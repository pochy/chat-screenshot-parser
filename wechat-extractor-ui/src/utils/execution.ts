import type { Node, Edge } from '@xyflow/react';
import type { NodeData, InputNodeData, ExtractNodeData, ProcessNodeData, TranslateNodeData } from '../types';
import { uploadImages, extractText, processMessages, translateMessages, parseJsonlToMessages } from './api';

/**
 * トポロジカルソートを実行し、ノードの実行順序を決定
 */
export function topologicalSort(nodes: Node<NodeData>[], edges: Edge[]): Node<NodeData>[] {
    // 各ノードの入次数を計算
    const inDegree = new Map<string, number>();
    const adjacencyList = new Map<string, string[]>();

    // 初期化
    nodes.forEach(node => {
        inDegree.set(node.id, 0);
        adjacencyList.set(node.id, []);
    });

    // エッジから隣接リストと入次数を構築
    edges.forEach(edge => {
        const from = edge.source;
        const to = edge.target;

        adjacencyList.get(from)?.push(to);
        inDegree.set(to, (inDegree.get(to) || 0) + 1);
    });

    // 入次数が0のノードをキューに追加
    const queue: string[] = [];
    inDegree.forEach((degree, nodeId) => {
        if (degree === 0) {
            queue.push(nodeId);
        }
    });

    // トポロジカルソート実行
    const sorted: Node<NodeData>[] = [];
    const nodeMap = new Map(nodes.map(n => [n.id, n]));

    while (queue.length > 0) {
        const nodeId = queue.shift()!;
        const node = nodeMap.get(nodeId);
        if (node) {
            sorted.push(node);
        }

        // 隣接ノードの入次数を減らす
        adjacencyList.get(nodeId)?.forEach(nextId => {
            const newDegree = (inDegree.get(nextId) || 0) - 1;
            inDegree.set(nextId, newDegree);

            if (newDegree === 0) {
                queue.push(nextId);
            }
        });
    }

    // サイクルチェック
    if (sorted.length !== nodes.length) {
        throw new Error('パイプラインに循環依存が検出されました');
    }

    return sorted;
}

/**
 * 前のノードから入力データを取得
 */
function getPreviousNodeResult(nodeId: string, nodes: Node<NodeData>[], edges: Edge[]): any {
    // このノードへの入力エッジを見つける
    const incomingEdge = edges.find(e => e.target === nodeId);
    if (!incomingEdge) {
        return null;
    }

    // 前のノードを見つける
    const previousNode = nodes.find(n => n.id === incomingEdge.source);
    return previousNode?.data.result;
}

/**
 * 個別のノードを実行
 */
export async function executeNode(
    node: Node<NodeData>,
    nodes: Node<NodeData>[],
    edges: Edge[],
    updateNodeStatus: (nodeId: string, status: NodeData['status']) => void,
    updateNodeResult: (nodeId: string, result: any) => void,
    updateNodeData: (nodeId: string, data: Partial<NodeData>) => void,
    addLog: (log: { nodeId: string; message: string; level: 'info' | 'warning' | 'error' }) => void
): Promise<void> {
    const { id, type, data } = node;

    try {
        updateNodeStatus(id, 'running');
        addLog({ nodeId: id, message: `${data.label}ノードの実行を開始しました`, level: 'info' });

        switch (type) {
            case 'input': {
                const inputData = data as InputNodeData;
                const files = inputData.config.images.map(img => img.file);

                if (files.length === 0) {
                    throw new Error('画像が選択されていません');
                }

                addLog({ nodeId: id, message: `${files.length}個の画像をアップロード中...`, level: 'info' });
                const result = await uploadImages(files);

                updateNodeResult(id, result);
                updateNodeStatus(id, 'success');
                addLog({ nodeId: id, message: `${result.uploadedPaths.length}個の画像をアップロードしました`, level: 'info' });
                break;
            }

            case 'extract': {
                const extractData = data as ExtractNodeData;
                const previousResult = getPreviousNodeResult(id, nodes, edges);

                if (!previousResult?.uploadedPaths) {
                    throw new Error('入力画像が見つかりません');
                }

                addLog({ nodeId: id, message: `OCR処理を実行中 (GPU: ${extractData.config.useGpu ? '有効' : '無効'})...`, level: 'info' });
                const result = await extractText({
                    images: previousResult.uploadedPaths,
                    useGpu: extractData.config.useGpu,
                });

                updateNodeResult(id, result);
                updateNodeStatus(id, 'success');
                addLog({ nodeId: id, message: `${result.messageCount}件のメッセージを抽出しました`, level: 'info' });
                break;
            }

            case 'process': {
                const processData = data as ProcessNodeData;
                const previousResult = getPreviousNodeResult(id, nodes, edges);

                if (!previousResult?.rawJsonl) {
                    throw new Error('入力データが見つかりません');
                }

                addLog({ nodeId: id, message: '重複除去と処理を実行中...', level: 'info' });
                const result = await processMessages({
                    inputJsonl: previousResult.rawJsonl,
                    similarityThreshold: processData.config.similarityThreshold,
                    useLlm: processData.config.useLlm,
                    llmModel: processData.config.llmModel,
                });

                updateNodeResult(id, result);
                updateNodeStatus(id, 'success');
                addLog({
                    nodeId: id,
                    message: `処理完了: ${result.messageCount}件のメッセージ (${result.duplicatesRemoved}件の重複を削除)`,
                    level: 'info'
                });
                break;
            }

            case 'translate': {
                const translateData = data as TranslateNodeData;
                const previousResult = getPreviousNodeResult(id, nodes, edges);

                if (!previousResult?.refinedJsonl) {
                    throw new Error('入力データが見つかりません');
                }

                addLog({ nodeId: id, message: `翻訳を実行中 (${translateData.config.backend}/${translateData.config.model})...`, level: 'info' });
                const result = await translateMessages({
                    inputJsonl: previousResult.refinedJsonl,
                    backend: translateData.config.backend,
                    model: translateData.config.model,
                    detailed: translateData.config.detailed,
                    batchSize: translateData.config.batchSize,
                });

                updateNodeResult(id, result);
                updateNodeStatus(id, 'success');
                addLog({ nodeId: id, message: `${result.messageCount}件のメッセージを翻訳しました`, level: 'info' });
                break;
            }

            case 'viewer': {
                const previousResult = getPreviousNodeResult(id, nodes, edges);

                if (!previousResult?.translatedJsonl) {
                    throw new Error('入力データが見つかりません');
                }

                addLog({ nodeId: id, message: 'メッセージを解析中...', level: 'info' });
                const messages = parseJsonlToMessages(previousResult.translatedJsonl);

                const stats = {
                    totalMessages: messages.length,
                    userAMessages: messages.filter(m => m.speaker === 'user_a').length,
                    userBMessages: messages.filter(m => m.speaker === 'user_b').length,
                };

                const result = { messages, stats };
                updateNodeResult(id, result);
                updateNodeStatus(id, 'success');
                addLog({ nodeId: id, message: `${messages.length}件のメッセージを表示準備完了`, level: 'info' });
                break;
            }

            default:
                throw new Error(`未知のノードタイプ: ${type}`);
        }

    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '不明なエラー';
        updateNodeStatus(id, 'error');
        updateNodeData(id, { error: errorMessage });
        addLog({ nodeId: id, message: `エラー: ${errorMessage}`, level: 'error' });
        throw error;
    }
}

/**
 * パイプライン全体を順次実行
 */
export async function executeAllNodes(
    nodes: Node<NodeData>[],
    edges: Edge[],
    updateNodeStatus: (nodeId: string, status: NodeData['status']) => void,
    updateNodeResult: (nodeId: string, result: any) => void,
    updateNodeData: (nodeId: string, data: Partial<NodeData>) => void,
    addLog: (log: { nodeId: string; message: string; level: 'info' | 'warning' | 'error' }) => void
): Promise<void> {
    try {
        addLog({ nodeId: 'system', message: 'パイプラインの実行を開始します', level: 'info' });

        // トポロジカルソートで実行順序を決定
        const sortedNodes = topologicalSort(nodes, edges);
        addLog({
            nodeId: 'system',
            message: `実行順序: ${sortedNodes.map(n => n.data.label).join(' → ')}`,
            level: 'info'
        });

        // 順次実行
        for (const node of sortedNodes) {
            await executeNode(node, nodes, edges, updateNodeStatus, updateNodeResult, updateNodeData, addLog);
        }

        addLog({ nodeId: 'system', message: 'パイプラインの実行が完了しました', level: 'info' });

    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : '不明なエラー';
        addLog({ nodeId: 'system', message: `パイプライン実行エラー: ${errorMessage}`, level: 'error' });
        throw error;
    }
}

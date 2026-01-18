import { useCallback } from 'react';
import type { NodeProps } from '@xyflow/react';
import { Languages } from 'lucide-react';
import { BaseNode } from './BaseNode';
import type { TranslateNodeData } from '../../types';
import { useFlowStore } from '../../store/flowStore';
import { translateMessages } from '../../utils/api';

export function TranslateNode({ id, data }: NodeProps<TranslateNodeData>) {
    const { nodes, edges, updateNodeData, updateNodeStatus, updateNodeResult, addLog } = useFlowStore();

    const getInputNode = useCallback(() => {
        const inputEdge = edges.find(e => e.target === id);
        if (!inputEdge) return null;
        return nodes.find(n => n.id === inputEdge.source);
    }, [id, nodes, edges]);

    const handleExecute = useCallback(async () => {
        const inputNode = getInputNode();
        if (!inputNode || inputNode.data.status !== 'success') {
            updateNodeData(id, { error: 'Process node must be executed successfully first' });
            return;
        }

        const refinedJsonl = inputNode.data.result?.refinedJsonl;
        if (!refinedJsonl) {
            updateNodeData(id, { error: 'No JSONL data available from process node' });
            return;
        }

        updateNodeStatus(id, 'running');
        updateNodeData(id, { error: undefined });
        addLog({ nodeId: id, message: `Translating with ${data.config.backend}...`, level: 'info' });

        try {
            const result = await translateMessages({
                inputJsonl: refinedJsonl,
                backend: data.config.backend,
                model: data.config.model,
                detailed: data.config.detailed,
                batchSize: data.config.backend === 'gemini-batch' ? data.config.batchSize : undefined,
            });

            updateNodeStatus(id, 'success');
            updateNodeResult(id, result);
            addLog({ nodeId: id, message: `Translated ${result.messageCount} messages`, level: 'info' });
        } catch (error) {
            updateNodeStatus(id, 'error');
            updateNodeData(id, { error: (error as Error).message });
            addLog({ nodeId: id, message: `Translation failed: ${(error as Error).message}`, level: 'error' });
        }
    }, [id, data.config, getInputNode, updateNodeData, updateNodeStatus, updateNodeResult, addLog]);

    const updateConfig = useCallback((updates: Partial<TranslateNodeData['config']>) => {
        updateNodeData(id, { config: { ...data.config, ...updates } });
    }, [id, data.config, updateNodeData]);

    const inputNode = getInputNode();
    const canExecute = inputNode?.data.status === 'success';

    return (
        <BaseNode
            id={id}
            title="Translate"
            icon={<Languages size={18} />}
            status={data.status}
            error={data.error}
            logs={data.logs}
            onExecute={handleExecute}
            canExecute={canExecute}
        >
            {/* Backend Selection */}
            <div className="space-y-1">
                <label className="text-sm text-gray-300">Backend</label>
                <select
                    value={data.config.backend}
                    onChange={(e) => updateConfig({ backend: e.target.value as any })}
                    className="w-full bg-dark-bg border border-dark-border rounded px-2 py-1.5 text-sm text-white"
                >
                    <option value="ollama">Ollama (Local)</option>
                    <option value="gemini">Gemini API</option>
                    <option value="gemini-batch">Gemini Batch (50% OFF)</option>
                </select>
            </div>

            {/* Model Selection */}
            <div className="space-y-1">
                <label className="text-sm text-gray-300">Model</label>
                <select
                    value={data.config.model}
                    onChange={(e) => updateConfig({ model: e.target.value })}
                    className="w-full bg-dark-bg border border-dark-border rounded px-2 py-1.5 text-sm text-white"
                >
                    {data.config.backend === 'ollama' ? (
                        <>
                            <option value="qwen2.5:7b">qwen2.5:7b</option>
                            <option value="qwen2.5:14b">qwen2.5:14b</option>
                            <option value="llama3:8b">llama3:8b</option>
                        </>
                    ) : (
                        <>
                            <option value="gemini-2.5-flash-lite">gemini-2.5-flash-lite</option>
                            <option value="gemini-2.0-flash">gemini-2.0-flash</option>
                            <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                        </>
                    )}
                </select>
            </div>

            {/* Detailed Mode Toggle */}
            {data.config.backend !== 'gemini-batch' && (
                <div className="flex items-center justify-between">
                    <label className="text-sm text-gray-300">Detailed Translation</label>
                    <button
                        onClick={() => updateConfig({ detailed: !data.config.detailed })}
                        className={`relative w-12 h-6 rounded-full transition-colors ${data.config.detailed ? 'bg-dark-accent' : 'bg-gray-600'
                            }`}
                    >
                        <div
                            className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${data.config.detailed ? 'translate-x-6' : 'translate-x-0'
                                }`}
                        />
                    </button>
                </div>
            )}

            {/* Batch Size */}
            {data.config.backend === 'gemini-batch' && (
                <div className="space-y-1">
                    <label className="text-sm text-gray-300">Batch Size</label>
                    <input
                        type="number"
                        min="100"
                        max="1000"
                        step="100"
                        value={data.config.batchSize || 1000}
                        onChange={(e) => updateConfig({ batchSize: parseInt(e.target.value) })}
                        className="w-full bg-dark-bg border border-dark-border rounded px-2 py-1.5 text-sm text-white"
                    />
                </div>
            )}

            {/* Result Preview */}
            {data.result && (
                <div className="bg-dark-bg rounded p-2 space-y-1">
                    <div className="text-xs text-gray-400">Result:</div>
                    <div className="text-sm text-green-400">
                        ✓ {data.result.messageCount} messages translated
                    </div>
                </div>
            )}
        </BaseNode>
    );
}

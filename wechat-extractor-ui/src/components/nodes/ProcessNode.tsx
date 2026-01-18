import { useCallback } from 'react';
import type { NodeProps } from '@xyflow/react';
import { Filter } from 'lucide-react';
import { BaseNode } from './BaseNode';
import type { ProcessNodeData } from '../../types';
import { useFlowStore } from '../../store/flowStore';
import { processMessages } from '../../utils/api';

export function ProcessNode({ id, data }: NodeProps<ProcessNodeData>) {
    const { nodes, edges, updateNodeData, updateNodeStatus, updateNodeResult, addLog } = useFlowStore();

    const getInputNode = useCallback(() => {
        const inputEdge = edges.find(e => e.target === id);
        if (!inputEdge) return null;
        return nodes.find(n => n.id === inputEdge.source);
    }, [id, nodes, edges]);

    const handleExecute = useCallback(async () => {
        const inputNode = getInputNode();
        if (!inputNode || inputNode.data.status !== 'success') {
            updateNodeData(id, { error: 'Extract node must be executed successfully first' });
            return;
        }

        const rawJsonl = inputNode.data.result?.rawJsonl;
        if (!rawJsonl) {
            updateNodeData(id, { error: 'No JSONL data available from extract node' });
            return;
        }

        updateNodeStatus(id, 'running');
        updateNodeData(id, { error: undefined });
        addLog({ nodeId: id, message: 'Processing messages (dedupe + refine)...', level: 'info' });

        try {
            const result = await processMessages({
                inputJsonl: rawJsonl,
                similarityThreshold: data.config.similarityThreshold,
                useLlm: data.config.useLlm,
                llmModel: data.config.useLlm ? data.config.llmModel : undefined,
            });

            updateNodeStatus(id, 'success');
            updateNodeResult(id, result);
            addLog({
                nodeId: id,
                message: `Processed ${result.messageCount} messages, removed ${result.duplicatesRemoved} duplicates`,
                level: 'info',
            });
        } catch (error) {
            updateNodeStatus(id, 'error');
            updateNodeData(id, { error: (error as Error).message });
            addLog({ nodeId: id, message: `Processing failed: ${(error as Error).message}`, level: 'error' });
        }
    }, [id, data.config, getInputNode, updateNodeData, updateNodeStatus, updateNodeResult, addLog]);

    const updateConfig = useCallback((updates: Partial<ProcessNodeData['config']>) => {
        updateNodeData(id, { config: { ...data.config, ...updates } });
    }, [id, data.config, updateNodeData]);

    const inputNode = getInputNode();
    const canExecute = inputNode?.data.status === 'success';

    return (
        <BaseNode
            id={id}
            title="Process (Dedupe + Refine)"
            icon={<Filter size={18} />}
            status={data.status}
            error={data.error}
            logs={data.logs}
            onExecute={handleExecute}
            canExecute={canExecute}
        >
            {/* Similarity Threshold */}
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <label className="text-sm text-gray-300">Similarity Threshold</label>
                    <span className="text-sm text-dark-accent font-mono">
                        {data.config.similarityThreshold.toFixed(2)}
                    </span>
                </div>
                <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={data.config.similarityThreshold}
                    onChange={(e) => updateConfig({ similarityThreshold: parseFloat(e.target.value) })}
                    className="w-full accent-dark-accent"
                />
            </div>

            {/* Use LLM Toggle */}
            <div className="flex items-center justify-between">
                <label className="text-sm text-gray-300">Use LLM for Quality Check</label>
                <button
                    onClick={() => updateConfig({ useLlm: !data.config.useLlm })}
                    className={`relative w-12 h-6 rounded-full transition-colors ${data.config.useLlm ? 'bg-dark-accent' : 'bg-gray-600'
                        }`}
                >
                    <div
                        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${data.config.useLlm ? 'translate-x-6' : 'translate-x-0'
                            }`}
                    />
                </button>
            </div>

            {/* LLM Model Selection */}
            {data.config.useLlm && (
                <div className="space-y-1">
                    <label className="text-sm text-gray-300">LLM Model</label>
                    <select
                        value={data.config.llmModel}
                        onChange={(e) => updateConfig({ llmModel: e.target.value })}
                        className="w-full bg-dark-bg border border-dark-border rounded px-2 py-1.5 text-sm text-white"
                    >
                        <option value="qwen2.5:7b">qwen2.5:7b</option>
                        <option value="qwen2.5:14b">qwen2.5:14b</option>
                        <option value="llama3:8b">llama3:8b</option>
                    </select>
                </div>
            )}

            {/* Result Preview */}
            {data.result && (
                <div className="bg-dark-bg rounded p-2 space-y-1">
                    <div className="text-xs text-gray-400">Result:</div>
                    <div className="text-sm text-green-400">
                        ✓ {data.result.messageCount} messages
                    </div>
                    <div className="text-sm text-yellow-400">
                        ⚠ {data.result.duplicatesRemoved} duplicates removed
                    </div>
                </div>
            )}
        </BaseNode>
    );
}

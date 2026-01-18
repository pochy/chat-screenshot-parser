import { useCallback } from 'react';
import type { NodeProps } from '@xyflow/react';
import { Scan } from 'lucide-react';
import { BaseNode } from './BaseNode';
import type { ExtractNodeData } from '../../types';
import { useFlowStore } from '../../store/flowStore';
import { extractText } from '../../utils/api';

export function ExtractNode({ id, data }: NodeProps<ExtractNodeData>) {
    const { nodes, updateNodeData, updateNodeStatus, updateNodeResult, addLog } = useFlowStore();

    const getInputNode = useCallback(() => {
        const edges = useFlowStore.getState().edges;
        const inputEdge = edges.find(e => e.target === id);
        if (!inputEdge) return null;
        return nodes.find(n => n.id === inputEdge.source);
    }, [id, nodes]);

    const handleExecute = useCallback(async () => {
        const inputNode = getInputNode();
        if (!inputNode || inputNode.data.status !== 'success') {
            updateNodeData(id, { error: 'Input node must be executed successfully first' });
            return;
        }

        const uploadedPaths = inputNode.data.result?.uploadedPaths;
        if (!uploadedPaths || uploadedPaths.length === 0) {
            updateNodeData(id, { error: 'No images available from input' });
            return;
        }

        updateNodeStatus(id, 'running');
        updateNodeData(id, { error: undefined });
        addLog({ nodeId: id, message: `Extracting text from ${uploadedPaths.length} images...`, level: 'info' });

        try {
            const result = await extractText({
                images: uploadedPaths,
                useGpu: data.config.useGpu,
            });

            updateNodeStatus(id, 'success');
            updateNodeResult(id, result);
            addLog({ nodeId: id, message: `Extracted ${result.messageCount} messages`, level: 'info' });
        } catch (error) {
            updateNodeStatus(id, 'error');
            updateNodeData(id, { error: (error as Error).message });
            addLog({ nodeId: id, message: `Extraction failed: ${(error as Error).message}`, level: 'error' });
        }
    }, [id, data.config.useGpu, getInputNode, updateNodeData, updateNodeStatus, updateNodeResult, addLog]);

    const toggleGpu = useCallback(() => {
        updateNodeData(id, {
            config: { ...data.config, useGpu: !data.config.useGpu },
        });
    }, [id, data.config, updateNodeData]);

    const inputNode = getInputNode();
    const canExecute = inputNode?.data.status === 'success';

    return (
        <BaseNode
            id={id}
            title="OCR Extract"
            icon={<Scan size={18} />}
            status={data.status}
            error={data.error}
            logs={data.logs}
            onExecute={handleExecute}
            canExecute={canExecute}
        >
            {/* GPU Toggle */}
            <div className="flex items-center justify-between">
                <label className="text-sm text-gray-300">Use GPU</label>
                <button
                    onClick={toggleGpu}
                    className={`relative w-12 h-6 rounded-full transition-colors ${data.config.useGpu ? 'bg-dark-accent' : 'bg-gray-600'
                        }`}
                >
                    <div
                        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform ${data.config.useGpu ? 'translate-x-6' : 'translate-x-0'
                            }`}
                    />
                </button>
            </div>

            {/* Result Preview */}
            {data.result && (
                <div className="bg-dark-bg rounded p-2 space-y-1">
                    <div className="text-xs text-gray-400">Result:</div>
                    <div className="text-sm text-green-400">
                        ✓ {data.result.messageCount} messages extracted
                    </div>
                </div>
            )}
        </BaseNode>
    );
}

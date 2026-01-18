import { Upload, Scan, Filter, Languages, Eye } from 'lucide-react';
import { useCallback } from 'react';
import { useReactFlow } from '@xyflow/react';
import type { NodeData } from '../types';

const nodeTypes = [
    { type: 'input', label: 'Input', icon: Upload, color: 'text-blue-400' },
    { type: 'extract', label: 'Extract', icon: Scan, color: 'text-green-400' },
    { type: 'process', label: 'Process', icon: Filter, color: 'text-yellow-400' },
    { type: 'translate', label: 'Translate', icon: Languages, color: 'text-purple-400' },
    { type: 'viewer', label: 'Viewer', icon: Eye, color: 'text-pink-400' },
];

const defaultConfigs: Record<string, any> = {
    input: { images: [] },
    extract: { useGpu: true },
    process: { similarityThreshold: 0.8, useLlm: false, llmModel: 'qwen2.5:7b' },
    translate: { backend: 'ollama', model: 'qwen2.5:7b', detailed: false },
    viewer: { searchQuery: '' },
};

export function Sidebar() {
    const { screenToFlowPosition, addNodes } = useReactFlow();

    const onDragStart = useCallback((event: React.DragEvent, nodeType: string) => {
        event.dataTransfer.setData('application/reactflow', nodeType);
        event.dataTransfer.effectAllowed = 'move';
    }, []);

    const handleAddNode = useCallback((nodeType: string) => {
        const position = screenToFlowPosition({ x: 400, y: 300 });
        const newNode = {
            id: `${nodeType}-${Date.now()}`,
            type: nodeType,
            position,
            data: {
                label: nodeType.charAt(0).toUpperCase() + nodeType.slice(1),
                status: 'idle' as const,
                config: defaultConfigs[nodeType] || {},
                logs: [],
            } as NodeData,
        };
        addNodes(newNode);
    }, [screenToFlowPosition, addNodes]);

    return (
        <div className="bg-dark-node border-r border-dark-border w-64 p-4 space-y-2">
            <h2 className="text-white font-bold text-lg mb-4">Node Palette</h2>

            {nodeTypes.map(({ type, label, icon: Icon, color }) => (
                <div
                    key={type}
                    draggable
                    onDragStart={(e) => onDragStart(e, type)}
                    onClick={() => handleAddNode(type)}
                    className="bg-dark-bg hover:bg-dark-hover border border-dark-border rounded-lg p-3 cursor-move transition-colors group"
                >
                    <div className="flex items-center gap-3">
                        <Icon className={`${color} group-hover:scale-110 transition-transform`} size={20} />
                        <span className="text-white font-medium">{label}</span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                        {type === 'input' && 'Upload images'}
                        {type === 'extract' && 'OCR extraction'}
                        {type === 'process' && 'Dedupe + Refine'}
                        {type === 'translate' && 'Translation'}
                        {type === 'viewer' && 'View results'}
                    </p>
                </div>
            ))}

            <div className="pt-4 border-t border-dark-border mt-4">
                <p className="text-xs text-gray-500 italic">
                    Drag nodes to canvas or click to add
                </p>
            </div>
        </div>
    );
}

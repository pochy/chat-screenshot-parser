import { useCallback, useEffect, useState } from 'react';
import type { NodeProps } from '@xyflow/react';
import { Eye, Download, Search } from 'lucide-react';
import { BaseNode } from './BaseNode';
import type { ViewerNodeData, ChatMessage } from '../../types';
import { useFlowStore } from '../../store/flowStore';
import { parseJsonlToMessages } from '../../utils/api';

export function ViewerNode({ id, data }: NodeProps<ViewerNodeData>) {
    const { nodes, edges, updateNodeData, updateNodeResult } = useFlowStore();
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [filteredMessages, setFilteredMessages] = useState<ChatMessage[]>([]);

    const getInputNode = useCallback(() => {
        const inputEdge = edges.find(e => e.target === id);
        if (!inputEdge) return null;
        return nodes.find(n => n.id === inputEdge.source);
    }, [id, nodes, edges]);

    // Auto-update when input changes
    useEffect(() => {
        const inputNode = getInputNode();
        if (inputNode?.data.status === 'success' && inputNode.data.result?.translatedJsonl) {
            const parsed = parseJsonlToMessages(inputNode.data.result.translatedJsonl);
            setMessages(parsed);
            setFilteredMessages(parsed);

            const stats = {
                totalMessages: parsed.length,
                userAMessages: parsed.filter(m => m.speaker === 'user_a').length,
                userBMessages: parsed.filter(m => m.speaker === 'user_b').length,
            };

            updateNodeResult(id, { messages: parsed, stats });
        }
    }, [getInputNode, id, updateNodeResult]);

    const handleSearch = useCallback((query: string) => {
        updateNodeData(id, { config: { searchQuery: query } });

        if (!query.trim()) {
            setFilteredMessages(messages);
            return;
        }

        const filtered = messages.filter(msg =>
            msg.text.toLowerCase().includes(query.toLowerCase()) ||
            msg.text_ja?.toLowerCase().includes(query.toLowerCase())
        );
        setFilteredMessages(filtered);
    }, [messages, id, updateNodeData]);

    const handleExport = useCallback(() => {
        const inputNode = getInputNode();
        if (!inputNode?.data.result?.translatedJsonl) return;

        const blob = new Blob([inputNode.data.result.translatedJsonl], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'translated_messages.jsonl';
        a.click();
        URL.revokeObjectURL(url);
    }, [getInputNode]);

    return (
        <BaseNode
            id={id}
            title="Viewer"
            icon={<Eye size={18} />}
            status={data.status}
            error={data.error}
            logs={data.logs}
            hasOutput={false}
            canExecute={false}
        >
            {/* Search Bar */}
            <div className="relative">
                <Search className="absolute left-2 top-2 text-gray-400" size={16} />
                <input
                    type="text"
                    placeholder="Search messages..."
                    value={data.config.searchQuery || ''}
                    onChange={(e) => handleSearch(e.target.value)}
                    className="w-full bg-dark-bg border border-dark-border rounded pl-8 pr-2 py-1.5 text-sm text-white placeholder-gray-500"
                />
            </div>

            {/* Stats */}
            {data.result?.stats && (
                <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="bg-dark-bg rounded p-2">
                        <div className="text-xs text-gray-400">Total</div>
                        <div className="text-lg font-bold text-white">{data.result.stats.totalMessages}</div>
                    </div>
                    <div className="bg-dark-bg rounded p-2">
                        <div className="text-xs text-gray-400">User A</div>
                        <div className="text-lg font-bold text-blue-400">{data.result.stats.userAMessages}</div>
                    </div>
                    <div className="bg-dark-bg rounded p-2">
                        <div className="text-xs text-gray-400">User B</div>
                        <div className="text-lg font-bold text-purple-400">{data.result.stats.userBMessages}</div>
                    </div>
                </div>
            )}

            {/* Chat Preview */}
            {filteredMessages.length > 0 && (
                <div className="bg-dark-bg rounded p-2 max-h-64 overflow-y-auto space-y-2">
                    {filteredMessages.slice(0, 10).map((msg) => (
                        <div
                            key={msg.id}
                            className={`flex ${msg.speaker === 'user_a' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[80%] rounded-lg p-2 ${msg.speaker === 'user_a'
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-gray-700 text-white'
                                    }`}
                            >
                                <div className="text-sm">{msg.text}</div>
                                {msg.text_ja && (
                                    <div className="text-xs text-gray-300 mt-1 border-t border-gray-500 pt-1">
                                        {msg.text_ja}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                    {filteredMessages.length > 10 && (
                        <div className="text-xs text-gray-400 text-center">
                            + {filteredMessages.length - 10} more messages
                        </div>
                    )}
                </div>
            )}

            {/* Export Button */}
            <button
                onClick={handleExport}
                disabled={!data.result}
                className="w-full bg-dark-accent hover:bg-green-400 disabled:bg-gray-600 disabled:cursor-not-allowed text-dark-bg font-medium py-2 rounded flex items-center justify-center gap-2 transition-colors"
            >
                <Download size={16} />
                Export JSONL
            </button>
        </BaseNode>
    );
}

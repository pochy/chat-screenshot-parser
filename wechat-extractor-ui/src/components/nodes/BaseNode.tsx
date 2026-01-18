import { ReactNode } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Play, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react';
import type { NodeStatus } from '../../types';

interface BaseNodeProps {
    id: string;
    title: string;
    icon: ReactNode;
    status: NodeStatus;
    error?: string;
    logs: string[];
    hasInput?: boolean;
    hasOutput?: boolean;
    onExecute?: () => void;
    canExecute?: boolean;
    children: ReactNode;
}

const statusColors = {
    idle: 'bg-gray-500',
    running: 'bg-yellow-500 animate-pulse',
    success: 'bg-green-500',
    error: 'bg-red-500',
};

const statusBorders = {
    idle: 'border-dark-border',
    running: 'border-yellow-500',
    success: 'border-green-500',
    error: 'border-red-500',
};

export function BaseNode({
    id,
    title,
    icon,
    status,
    error,
    logs,
    hasInput = true,
    hasOutput = true,
    onExecute,
    canExecute = true,
    children,
}: BaseNodeProps) {
    const [expanded, setExpanded] = useState(true);

    return (
        <div className={`bg-dark-node border-2 ${statusBorders[status]} rounded-lg shadow-xl min-w-[320px] max-w-[400px]`}>
            {/* Input Handle */}
            {hasInput && (
                <Handle
                    type="target"
                    position={Position.Left}
                    className="w-3 h-3 !bg-dark-accent border-2 border-dark-bg"
                />
            )}

            {/* Title Bar */}
            <div className="bg-dark-bg px-4 py-3 rounded-t-lg border-b border-dark-border flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${statusColors[status]}`} />
                    <div className="text-dark-accent">{icon}</div>
                    <span className="text-white font-medium">{title}</span>
                </div>
                <div className="flex items-center gap-2">
                    {onExecute && (
                        <button
                            onClick={onExecute}
                            disabled={!canExecute || status === 'running'}
                            className="p-1.5 rounded bg-dark-accent hover:bg-green-400 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
                            title="Execute"
                        >
                            <Play size={14} className="text-dark-bg" />
                        </button>
                    )}
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="p-1 rounded hover:bg-dark-hover transition-colors"
                    >
                        {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
                    </button>
                </div>
            </div>

            {/* Content */}
            {expanded && (
                <div className="p-4 space-y-3">
                    {children}

                    {/* Error Display */}
                    {error && (
                        <div className="bg-red-900/30 border border-red-500 rounded p-2 flex items-start gap-2">
                            <AlertCircle size={16} className="text-red-500 mt-0.5 flex-shrink-0" />
                            <span className="text-red-200 text-sm">{error}</span>
                        </div>
                    )}

                    {/* Mini Logs */}
                    {logs.length > 0 && (
                        <div className="bg-dark-bg rounded p-2 space-y-1 max-h-24 overflow-y-auto">
                            <div className="text-xs text-gray-400 font-medium mb-1">Recent Logs:</div>
                            {logs.slice(-3).map((log, i) => (
                                <div key={i} className="text-xs text-gray-300 font-mono">
                                    {log}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Output Handle */}
            {hasOutput && (
                <Handle
                    type="source"
                    position={Position.Right}
                    className={`w-3 h-3 border-2 border-dark-bg ${status === 'success' ? '!bg-green-500' : '!bg-dark-accent'
                        }`}
                />
            )}
        </div>
    );
}

import { useState } from 'react';

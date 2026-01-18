import { X, Trash2 } from 'lucide-react';
import { useFlowStore } from '../store/flowStore';

interface LogPanelProps {
    isOpen: boolean;
    onClose: () => void;
}

const levelColors = {
    info: 'text-blue-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
};

const levelIcons = {
    info: 'ℹ',
    warning: '⚠',
    error: '✕',
};

export function LogPanel({ isOpen, onClose }: LogPanelProps) {
    const { logs, clearLogs } = useFlowStore();

    if (!isOpen) return null;

    return (
        <div className="fixed bottom-0 left-0 right-0 bg-dark-node border-t border-dark-border shadow-2xl z-50 animate-slide-up">
            <div className="flex items-center justify-between px-4 py-2 border-b border-dark-border">
                <h3 className="text-white font-bold">Execution Logs</h3>
                <div className="flex items-center gap-2">
                    <button
                        onClick={clearLogs}
                        className="p-1.5 hover:bg-dark-hover rounded transition-colors"
                        title="Clear logs"
                    >
                        <Trash2 size={16} className="text-gray-400" />
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1.5 hover:bg-dark-hover rounded transition-colors"
                    >
                        <X size={16} className="text-gray-400" />
                    </button>
                </div>
            </div>

            <div className="h-64 overflow-y-auto p-4 space-y-2 font-mono text-sm">
                {logs.length === 0 ? (
                    <div className="text-gray-500 text-center py-8">No logs yet</div>
                ) : (
                    logs.map((log, i) => (
                        <div key={i} className="flex items-start gap-3 hover:bg-dark-hover p-2 rounded">
                            <span className={`${levelColors[log.level]} font-bold flex-shrink-0`}>
                                {levelIcons[log.level]}
                            </span>
                            <span className="text-gray-500 flex-shrink-0 text-xs">
                                {new Date(log.timestamp).toLocaleTimeString()}
                            </span>
                            <span className="text-gray-400 flex-shrink-0 text-xs">
                                [{log.nodeId}]
                            </span>
                            <span className="text-white flex-1">{log.message}</span>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

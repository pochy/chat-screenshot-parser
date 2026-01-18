import { Save, FolderOpen, Play, FileText } from 'lucide-react';
import { useFlowStore } from '../store/flowStore';
import { useState } from 'react';

interface TopbarProps {
    onRunAll: () => void;
    onToggleLogs: () => void;
}

export function Topbar({ onRunAll, onToggleLogs }: TopbarProps) {
    const { flowName, setFlowName, saveFlow, loadFlow } = useFlowStore();
    const [isEditing, setIsEditing] = useState(false);

    return (
        <div className="bg-dark-node border-b border-dark-border px-4 py-3 flex items-center justify-between">
            {/* Flow Name */}
            <div className="flex items-center gap-3">
                {isEditing ? (
                    <input
                        type="text"
                        value={flowName}
                        onChange={(e) => setFlowName(e.target.value)}
                        onBlur={() => setIsEditing(false)}
                        onKeyDown={(e) => e.key === 'Enter' && setIsEditing(false)}
                        autoFocus
                        className="bg-dark-bg border border-dark-accent rounded px-3 py-1.5 text-white font-medium"
                    />
                ) : (
                    <h1
                        onClick={() => setIsEditing(true)}
                        className="text-xl font-bold text-white cursor-pointer hover:text-dark-accent transition-colors"
                    >
                        {flowName}
                    </h1>
                )}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
                <button
                    onClick={saveFlow}
                    className="flex items-center gap-2 px-3 py-1.5 bg-dark-bg hover:bg-dark-hover border border-dark-border rounded text-white text-sm transition-colors"
                >
                    <Save size={16} />
                    Save
                </button>

                <button
                    onClick={loadFlow}
                    className="flex items-center gap-2 px-3 py-1.5 bg-dark-bg hover:bg-dark-hover border border-dark-border rounded text-white text-sm transition-colors"
                >
                    <FolderOpen size={16} />
                    Load
                </button>

                <button
                    onClick={onRunAll}
                    className="flex items-center gap-2 px-4 py-1.5 bg-dark-accent hover:bg-green-400 rounded text-dark-bg font-medium text-sm transition-colors"
                >
                    <Play size={16} />
                    Run All
                </button>

                <button
                    onClick={onToggleLogs}
                    className="flex items-center gap-2 px-3 py-1.5 bg-dark-bg hover:bg-dark-hover border border-dark-border rounded text-white text-sm transition-colors"
                >
                    <FileText size={16} />
                    Logs
                </button>
            </div>
        </div>
    );
}

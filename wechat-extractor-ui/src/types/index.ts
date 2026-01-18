export type NodeStatus = 'idle' | 'running' | 'success' | 'error';

export type NodeType = 'input' | 'extract' | 'process' | 'translate' | 'viewer';

export interface LogEntry {
    timestamp: string;
    nodeId: string;
    message: string;
    level: 'info' | 'warning' | 'error';
}

export interface ImageFile {
    id: string;
    file: File;
    preview: string;
}

export interface NodeData {
    label: string;
    status: NodeStatus;
    error?: string;
    config: Record<string, any>;
    result?: any;
    logs: string[];
}

export interface InputNodeData extends NodeData {
    config: {
        images: ImageFile[];
    };
    result?: {
        uploadedPaths: string[];
    };
}

export interface ExtractNodeData extends NodeData {
    config: {
        useGpu: boolean;
    };
    result?: {
        rawJsonl: string;
        messageCount: number;
    };
}

export interface ProcessNodeData extends NodeData {
    config: {
        similarityThreshold: number;
        useLlm: boolean;
        llmModel: string;
    };
    result?: {
        refinedJsonl: string;
        messageCount: number;
        duplicatesRemoved: number;
    };
}

export interface TranslateNodeData extends NodeData {
    config: {
        backend: 'ollama' | 'gemini' | 'gemini-batch';
        model: string;
        detailed: boolean;
        batchSize?: number;
    };
    result?: {
        translatedJsonl: string;
        messageCount: number;
    };
}

export interface ViewerNodeData extends NodeData {
    config: {
        searchQuery: string;
    };
    result?: {
        messages: ChatMessage[];
        stats: {
            totalMessages: number;
            userAMessages: number;
            userBMessages: number;
        };
    };
}

export interface ChatMessage {
    id: string;
    speaker: 'user_a' | 'user_b' | 'system';
    lang: 'ja' | 'zh' | 'system';
    text: string;
    text_ja?: string;
    text_ja_detailed?: string;
    timestamp?: string;
}

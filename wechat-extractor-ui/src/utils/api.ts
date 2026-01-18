import type { NodeData, ChatMessage } from '../types';

const USE_MOCK = !import.meta.env.VITE_API_URL;
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Mock delay helper
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Mock data generators
const generateMockJsonl = (count: number): string => {
    const messages = [];
    for (let i = 0; i < count; i++) {
        messages.push({
            id: `msg_${String(i).padStart(6, '0')}`,
            speaker: i % 2 === 0 ? 'user_a' : 'user_b',
            lang: i % 2 === 0 ? 'ja' : 'zh',
            text: i % 2 === 0 ? 'こんにちは' : '你好',
            confidence: 0.95 + Math.random() * 0.05,
        });
    }
    return messages.map(m => JSON.stringify(m)).join('\n');
};

const generateMockMessages = (jsonl: string): ChatMessage[] => {
    return jsonl.split('\n').filter(Boolean).map(line => {
        const msg = JSON.parse(line);
        return {
            ...msg,
            text_ja: msg.lang === 'zh' ? 'こんにちは（翻訳）' : undefined,
        };
    });
};

// API functions
export async function uploadImages(images: File[]): Promise<{ uploadedPaths: string[] }> {
    if (USE_MOCK) {
        await delay(1500);
        return {
            uploadedPaths: images.map((_, i) => `/uploads/image_${i}.png`),
        };
    }

    const formData = new FormData();
    images.forEach(img => formData.append('files', img));

    const response = await fetch(`${API_URL}/upload-images`, {
        method: 'POST',
        body: formData,
    });

    return response.json();
}

export async function extractText(config: { images: string[]; useGpu: boolean }): Promise<{ rawJsonl: string; messageCount: number }> {
    if (USE_MOCK) {
        await delay(2000);
        const rawJsonl = generateMockJsonl(50);
        return {
            rawJsonl,
            messageCount: 50,
        };
    }

    const response = await fetch(`${API_URL}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });

    return response.json();
}

export async function processMessages(config: {
    inputJsonl: string;
    similarityThreshold: number;
    useLlm: boolean;
    llmModel?: string;
}): Promise<{ refinedJsonl: string; messageCount: number; duplicatesRemoved: number }> {
    if (USE_MOCK) {
        await delay(1500);
        const lines = config.inputJsonl.split('\n').filter(Boolean);
        const duplicatesRemoved = Math.floor(lines.length * 0.1);
        const refinedJsonl = lines.slice(0, -duplicatesRemoved).join('\n');
        return {
            refinedJsonl,
            messageCount: lines.length - duplicatesRemoved,
            duplicatesRemoved,
        };
    }

    const response = await fetch(`${API_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });

    return response.json();
}

export async function translateMessages(config: {
    inputJsonl: string;
    backend: string;
    model: string;
    detailed: boolean;
    batchSize?: number;
}): Promise<{ translatedJsonl: string; messageCount: number }> {
    if (USE_MOCK) {
        await delay(2500);
        const lines = config.inputJsonl.split('\n').filter(Boolean);
        const translated = lines.map(line => {
            const msg = JSON.parse(line);
            if (msg.lang === 'zh') {
                msg.text_ja = 'こんにちは（翻訳済み）';
                if (config.detailed) {
                    msg.text_ja_detailed = '## 原文\n\n你好\n\n## 日本語訳\n\nこんにちは';
                }
            }
            return JSON.stringify(msg);
        });
        return {
            translatedJsonl: translated.join('\n'),
            messageCount: lines.length,
        };
    }

    const response = await fetch(`${API_URL}/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });

    return response.json();
}

export function parseJsonlToMessages(jsonl: string): ChatMessage[] {
    if (USE_MOCK) {
        return generateMockMessages(jsonl);
    }

    return jsonl.split('\n').filter(Boolean).map(line => JSON.parse(line));
}

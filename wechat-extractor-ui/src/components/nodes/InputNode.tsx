import { useCallback, useState } from 'react';
import type { NodeProps } from '@xyflow/react';
import { Upload, Image as ImageIcon, X } from 'lucide-react';
import { BaseNode } from './BaseNode';
import type { InputNodeData, ImageFile } from '../../types';
import { useFlowStore } from '../../store/flowStore';
import { uploadImages } from '../../utils/api';

export function InputNode({ id, data }: NodeProps<InputNodeData>) {
    const { updateNodeData, updateNodeStatus, updateNodeResult, addLog } = useFlowStore();
    const [images, setImages] = useState<ImageFile[]>(data.config.images || []);

    const handleFileSelect = useCallback((files: FileList | null) => {
        if (!files) return;

        const newImages: ImageFile[] = Array.from(files).map((file) => ({
            id: Math.random().toString(36).substr(2, 9),
            file,
            preview: URL.createObjectURL(file),
        }));

        const updated = [...images, ...newImages].slice(0, 12); // Max 12 images
        setImages(updated);
        updateNodeData(id, { config: { images: updated } });
    }, [images, id, updateNodeData]);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        handleFileSelect(e.dataTransfer.files);
    }, [handleFileSelect]);

    const handleRemoveImage = useCallback((imageId: string) => {
        const updated = images.filter(img => img.id !== imageId);
        setImages(updated);
        updateNodeData(id, { config: { images: updated } });
    }, [images, id, updateNodeData]);

    const handleExecute = useCallback(async () => {
        if (images.length === 0) {
            updateNodeData(id, { error: 'No images selected' });
            return;
        }

        updateNodeStatus(id, 'running');
        updateNodeData(id, { error: undefined });
        addLog({ nodeId: id, message: `Uploading ${images.length} images...`, level: 'info' });

        try {
            const result = await uploadImages(images.map(img => img.file));

            updateNodeStatus(id, 'success');
            updateNodeResult(id, result);
            addLog({ nodeId: id, message: `Successfully uploaded ${images.length} images`, level: 'info' });
        } catch (error) {
            updateNodeStatus(id, 'error');
            updateNodeData(id, { error: (error as Error).message });
            addLog({ nodeId: id, message: `Upload failed: ${(error as Error).message}`, level: 'error' });
        }
    }, [images, id, updateNodeData, updateNodeStatus, updateNodeResult, addLog]);

    return (
        <BaseNode
            id={id}
            title="Image Input"
            icon={<ImageIcon size={18} />}
            status={data.status}
            error={data.error}
            logs={data.logs}
            hasInput={false}
            onExecute={handleExecute}
            canExecute={images.length > 0}
        >
            {/* Drag & Drop Area */}
            <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="border-2 border-dashed border-dark-border hover:border-dark-accent rounded-lg p-6 text-center transition-colors cursor-pointer"
                onClick={() => document.getElementById(`file-input-${id}`)?.click()}
            >
                <Upload className="mx-auto mb-2 text-gray-400" size={32} />
                <p className="text-sm text-gray-300 mb-1">Drag & drop images here</p>
                <p className="text-xs text-gray-500">or click to browse</p>
                <input
                    id={`file-input-${id}`}
                    type="file"
                    multiple
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => handleFileSelect(e.target.files)}
                />
            </div>

            {/* Thumbnail Grid */}
            {images.length > 0 && (
                <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
                    {images.map((img) => (
                        <div key={img.id} className="relative group">
                            <img
                                src={img.preview}
                                alt="Preview"
                                className="w-full h-20 object-cover rounded border border-dark-border"
                            />
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleRemoveImage(img.id);
                                }}
                                className="absolute top-1 right-1 p-1 bg-red-500 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                                <X size={12} className="text-white" />
                            </button>
                        </div>
                    ))}
                </div>
            )}

            {/* Image Count */}
            <div className="text-xs text-gray-400 text-center">
                {images.length} / 12 images
            </div>
        </BaseNode>
    );
}

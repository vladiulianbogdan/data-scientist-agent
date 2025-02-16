import React, { useState, useRef } from 'react';
import { Send, Paperclip, X } from 'lucide-react';

interface Message {
  text: string;
  sender: 'user' | 'agent';
  files?: FileInfo[];
  images?: string[];
}

interface FileInfo {
  name: string;
  data: Blob;
  type: string;
}

const LOADING_MESSAGE: Message = { text: 'Loading...', sender: 'agent' };

const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState<string>('');
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleSend = async (): Promise<void> => {
    if (!input.trim() && files.length === 0) return;

    const newMessage: Message = { text: input, sender: 'user', files };
    setMessages([...messages, newMessage]);

    // Clear input and files immediately
    setInput('');
    setFiles([]);
    setIsLoading(true);
    setMessages((prev) => [...prev, LOADING_MESSAGE]);

    try {
      // API request
      const answers: any = await sendMessageToServer(newMessage);
      setMessages((prev) => [
        ...prev.filter((msg) => msg !== LOADING_MESSAGE),
        ...answers,
      ]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages((prev) => [
        ...prev.filter((msg) => msg !== LOADING_MESSAGE),
        {
          text: '❌ Error: Failed to send message. Please try again.',
          sender: 'agent',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFiles = (newFiles: FileList): void => {
    const fileList: FileInfo[] = Array.from(newFiles).map((file) => ({
      name: file.name,
      data: new Blob([file], { type: file.type }),
      type: file.type,
    }));
    setFiles((prevFiles) => [...prevFiles, ...fileList]);
  };

  const removeFile = (index: number): void => {
    setFiles((prevFiles) => prevFiles.filter((_, i) => i !== index));
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(true);
  };

  const sendMessageToServer = async (message: Message) => {
    const formData = new FormData();
    formData.append('input', message.text);

    if (message.files) {
      for (const file of message.files) {
        formData.append('files', file.data, file.name);
      }
    }

    const response = await fetch(
      import.meta.env.VITE_API_URL_FASTAPI + '/generate',
      {
        method: 'POST',
        body: formData,
      }
    );

    if (!response.ok) {
      throw new Error(`Server error: ${response.statusText}`);
    }

    const responseData = await response.json();

    // Extract messages and files
    const receivedMessage: Message = {
      text: responseData.messages[responseData.messages.length - 1],
      sender: 'agent',
      files: [],
      images: [],
    };

    for (const x of Object.keys(responseData.files)) {
      receivedMessage.images!.push(
        'data:image/png;base64,' + responseData.files[x]
      );
    }

    return [receivedMessage];
  };

  const MessageContent: React.FC<{ message: Message }> = ({ message }) => (
    <div
      className={`inline-block p-3 rounded-lg ${
        message.sender === 'user'
          ? 'bg-blue-500 text-white'
          : 'bg-gray-200 text-gray-800'
      }`}
    >
      <div>{message.text}</div>

      {message.images && (
        <div className="mt-2">
          {message.images.map((img, i) => (
            <img
              key={i}
              src={img}
              alt="Response image"
              className="max-w-full rounded mt-2"
            />
          ))}
        </div>
      )}

      {message.files && (
        <div className="text-sm mt-2">
          {message.files.map((file, i) => (
            <div key={i} className="text-xs">
              {file.name}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto p-4">
      <div
        className={`flex-1 overflow-y-auto mb-4 p-4 border rounded-lg ${
          isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
        }`}
        onDrop={handleFileDrop}
        onDragOver={handleDragOver}
        onDragLeave={() => setIsDragging(false)}
      >
        {messages.map((message, index) => (
          <div
            key={index}
            className={`mb-4 ${
              message.sender === 'user' ? 'text-right' : 'text-left'
            }`}
          >
            <MessageContent message={message} />
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
          multiple
        />
        <button
          className="p-2 hover:bg-gray-100 rounded"
          onClick={() => fileInputRef.current?.click()}
        >
          <Paperclip size={20} />
        </button>
        <input
          type="text"
          value={input}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setInput(e.target.value)
          }
          onKeyPress={(e: React.KeyboardEvent) =>
            e.key === 'Enter' && handleSend()
          }
          placeholder="Type a message..."
          className="flex-1 p-2 border rounded"
        />
        <button
          onClick={handleSend}
          disabled={isLoading}
          className="p-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          <Send size={20} />
        </button>
      </div>

      {files.length > 0 && (
        <div className="mt-2 p-2 border rounded-lg bg-gray-100 text-sm">
          <strong>Attached files:</strong>
          {files.map((file, index) => (
            <div
              key={index}
              className="flex items-center justify-between text-xs"
            >
              {file.name}
              <button
                onClick={() => removeFile(index)}
                className="text-red-500 ml-2"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ChatInterface;

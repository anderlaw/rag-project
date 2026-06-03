import { Upload } from "lucide-react";
import { useRef, useState } from "react";

import { ButtonSpinner } from "../../../components/common/ButtonSpinner";

type DocumentUploadCardProps = {
  title?: string;
  pending?: boolean;
  onUpload: (file: File) => void;
};

export function DocumentUploadCard({ title = "上传文档", pending = false, onUpload }: DocumentUploadCardProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);

  function pickFile(fileList: FileList | null) {
    if (pending) {
      return;
    }
    const file = fileList?.[0];
    if (file) {
      onUpload(file);
    }
  }

  return (
    <section
      className={`upload-card ${dragActive ? "upload-card-active" : ""}`}
      onDragEnter={(event) => {
        event.preventDefault();
        if (pending) {
          return;
        }
        setDragActive(true);
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={() => setDragActive(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragActive(false);
        pickFile(event.dataTransfer.files);
      }}
    >
      <div className="upload-icon" aria-hidden="true">
        <Upload size={22} />
      </div>
      <div>
        <h2>{title}</h2>
        <p>支持 txt、md、pdf、docx</p>
      </div>
      <button
        className="button button-primary"
        type="button"
        disabled={pending}
        aria-label={pending ? "处理中" : undefined}
        onClick={() => inputRef.current?.click()}
      >
        {pending ? <ButtonSpinner label="上传处理中" /> : <Upload size={16} />}
        {pending ? "处理中" : "选择文件"}
      </button>
      <input
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept=".txt,.md,.pdf,.docx"
        disabled={pending}
        onChange={(event) => pickFile(event.currentTarget.files)}
      />
    </section>
  );
}

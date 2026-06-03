import { FileQuestion } from "lucide-react";

type DocumentVersionEvalDraftButtonProps = {
  versionId?: number | null;
};

export function DocumentVersionEvalDraftButton({ versionId }: DocumentVersionEvalDraftButtonProps) {
  return (
    <button
      className="button button-secondary"
      type="button"
      disabled
      title={
        versionId
          ? "后端草稿生成接口接入后可用"
          : "当前文档没有可生成草稿的已完成版本"
      }
    >
      <FileQuestion size={16} />
      生成测试用例草稿
    </button>
  );
}

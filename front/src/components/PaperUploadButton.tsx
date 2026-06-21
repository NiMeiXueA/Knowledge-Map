type Props = {
  onClick: () => void;
};

export function PaperUploadButton({ onClick }: Props) {
  return (
    <button className="hero-action-btn hero-network-btn" type="button" onClick={onClick}>
      添加论文
    </button>
  );
}


// 차트 크게 보기 단추(2026-11-27). 사진 스크립트(uishots.py)가 이 이름(aria-label)으로 누른다
export function ZoomButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-label="차트 크게 보기"
      className="-my-2 inline-flex min-h-10 shrink-0 items-center gap-1 rounded-sm px-2 text-caption1 font-bold text-fg-2 hover:text-fg focus-visible:outline-2 focus-visible:outline-brand">
      크게 보기
      <svg aria-hidden width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M7 1.5h3.5V5M5 10.5H1.5V7M10.5 1.5 7 5M1.5 10.5 5 7" /></svg>
    </button>
  )
}

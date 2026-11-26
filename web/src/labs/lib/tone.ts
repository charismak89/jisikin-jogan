// 등락 색 클래스(표준 A: text-up, text-down, text-flat). 메인의 lib/fmt.ts dir() 는 옛 이름(text-dn)이라 실험실은 이것을 쓴다.
// 0 과 값 없음은 보합색이 아니라 본문색으로 둔다(옛 dir() 와 같은 동작)
export const tone = (p: number | null | undefined) => (p == null ? '' : p < 0 ? 'text-down' : p > 0 ? 'text-up' : '')

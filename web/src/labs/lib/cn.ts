import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// 표준 A 의 cn. 몽타주 글자 크기(text-caption1 등)를 tailwind-merge 가 색으로 오인해 text-fg 와 겹치면 지운다.
// 글자 크기 이름을 알려 줘서 둘 다 남긴다(2026-11-26 확인: 모의투자 봇 원본 cn 은 Badge 의 text-caption1 을 지운다)
const twMerge = extendTailwindMerge({
  extend: { classGroups: { 'font-size': [{ text: ['title1', 'title3', 'heading2', 'headline1', 'body1', 'body2', 'label1', 'label2', 'caption1'] }] } },
})
export const cn = (...a: ClassValue[]) => twMerge(clsx(a))

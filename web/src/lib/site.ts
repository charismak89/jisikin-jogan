// 저장소 루트 기준 주소. 앱 스크립트는 언제나 v6/assets/ 또는 labs/assets/(실험실)에 있으니 스크립트 위치에서 두 단계 올라가면 루트다.
// 루트(/jisikin-jogan/)에서 열든 /v6/ 에서 열든 같은 파일을 가리킨다(2026-10-19 메인 전환).
/** 화면 버전(web/versions.json). '7.0-beta.1' → 'v7.0 beta.1' */
import V from '../../versions.json'
export const versions = { main: V.main, labs: V.labs }
export const vlabel = (v: string) => 'v' + v.replace('-beta.', ' beta.')
export const site = (p: string) => new URL('../../' + p, import.meta.url).href

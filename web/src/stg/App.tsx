import MainApp from '../App'

// 시험 화면 첫 판은 메인과 같은 화면에 띠만 붙인다. 새 첫 카드는 이 파일에서 바꾼다
export default function App() {
  return (
    <>
      <div role="note" className="bg-tx px-4 py-1.5 text-center text-[12px] font-semibold text-bg">시험 화면(stg) · 메인 주소와 다를 수 있습니다</div>
      <MainApp />
    </>
  )
}

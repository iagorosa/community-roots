import { Link } from 'react-router'

/**
 * The site's front door (issue #19): explains the project in plain
 * language and gets a first-time visitor — a child, a parent, a teacher —
 * to the map. No technical vocabulary here (docs/architecture.md §8):
 * "canteiro" is the only word used for what the rest of the codebase
 * calls a "region".
 */
function HomePage() {
  return (
    <div className="flex flex-1 flex-col items-center bg-slate-50 px-4 py-12">
      <div className="max-w-2xl text-center">
        <h1 className="text-4xl font-bold text-emerald-700">Community Roots</h1>

        <p className="mt-4 text-lg text-slate-700">
          O Community Roots é um projeto para cuidar de plantas em canteiros espalhados pela nossa cidade. Cada
          canteiro é cuidado por pessoas da vizinhança e ajuda a deixar o ar mais limpo, o solo mais saudável e o
          bairro mais verde.
        </p>

        <p className="mt-4 text-lg text-slate-700">
          Você pode visitar um canteiro perto de você, ver fotos de como as plantas estão crescendo e escanear o QR
          Code que fica no local para conhecer a história daquele canteiro.
        </p>

        {/* `bg-emerald-700`, not `-600` (issue #35): white text on `-600`
            measures 3.77:1, under WCAG AA's 4.5:1 floor — `-700` clears it
            at 5.48:1. Hover darkens further to `-800` to stay distinct. */}
        <Link
          to="/mapa"
          className="mt-8 inline-block rounded-lg bg-emerald-700 px-6 py-3 text-lg font-semibold text-white shadow-md transition-colors hover:bg-emerald-800"
        >
          Ver o mapa dos canteiros
        </Link>
      </div>
    </div>
  )
}

export default HomePage

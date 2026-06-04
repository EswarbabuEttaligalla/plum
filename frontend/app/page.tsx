import Link from 'next/link'

export default function Home() {
  return (
    <main>
      <h1 className="text-2xl font-bold mb-4">Plum Claims Demo</h1>
      <div className="space-x-4">
        <Link href="/upload" className="px-4 py-2 bg-blue-600 text-white rounded">Upload Claim</Link>
        <Link href="/claims" className="px-4 py-2 bg-gray-200 rounded">Claims List</Link>
      </div>
    </main>
  )
}

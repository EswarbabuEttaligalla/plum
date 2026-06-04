import './globals.css'

export const metadata = {
  title: 'Plum Claims',
  description: 'Claim submission and adjudication UI',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="p-6 bg-gray-50">
        <div className="max-w-4xl mx-auto">{children}</div>
      </body>
    </html>
  )
}

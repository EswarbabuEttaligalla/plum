"use client"

import { useEffect, useState } from 'react'
import axios from 'axios'
import Link from 'next/link'

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000'

export default function ClaimsList() {
  const [claims, setClaims] = useState<any[]>([])

  useEffect(()=>{
    axios.get(`${apiBase}/api/claims/`).then(r=>setClaims(r.data.claims)).catch(()=>setClaims([]))
  },[])

  return (
    <main>
      <h2 className="text-xl font-semibold mb-4">Claims</h2>
      <table className="w-full bg-white rounded">
        <thead>
          <tr className="text-left"><th className="p-2">ID</th><th className="p-2">Status</th><th className="p-2">Amount</th><th className="p-2">Date</th></tr>
        </thead>
        <tbody>
          {claims.map(c=> (
            <tr key={c.id} className="border-t">
              <td className="p-2"><Link href={`/claims/${c.id}`}>{c.claim_code}</Link></td>
              <td className="p-2">{c.status}</td>
              <td className="p-2">{c.total_amount}</td>
              <td className="p-2">{new Date(c.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  )
}

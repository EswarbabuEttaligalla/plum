"use client"

import { useState } from "react"
import axios from "axios"

const apiBase =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000"

export default function UploadPage() {
  const [member, setMember] = useState("")
  const [amount, setAmount] = useState<number | string>("")
  const [billFile, setBillFile] = useState<File | null>(null)
  const [prescriptionFile, setPrescriptionFile] = useState<File | null>(null)
  const [reportFile, setReportFile] = useState<File | null>(null)
  const [message, setMessage] = useState("")

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    try {
      const resp = await axios.post(`${apiBase}/api/claims/`, {
        member_code: member,
        treatment_date: new Date().toISOString().slice(0, 10),
        items: [
          {
            description: "consultation",
            amount: Number(amount),
            category: "consultation_fees",
          },
        ],
        total_amount: Number(amount),
      })

      const id = resp.data.id

      const uploads: Array<{ file: File | null; docType: string }> = [
        { file: billFile, docType: "original_bills" },
        { file: prescriptionFile, docType: "prescription" },
        { file: reportFile, docType: "medical_report" },
      ]

      for (const upload of uploads) {
        if (!upload.file) continue

        const form = new FormData()
        form.append("file", upload.file)
        form.append("doc_type", upload.docType)

        await axios.post(
          `${apiBase}/api/claims/${id}/upload`,
          form,
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
          }
        )
      }

      const dec = await axios.post(
        `${apiBase}/api/claims/${id}/process`
      )

      setMessage(JSON.stringify(dec.data, null, 2))

      setTimeout(() => {
        setMember("")
        setAmount("")
        setBillFile(null)
        setPrescriptionFile(null)
        setReportFile(null)

        window.location.reload()
      }, 2000)
    } catch (err: any) {
      setMessage(
        err?.response?.data?.detail ||
          err?.message ||
          String(err)
      )
    }
  }

  return (
    <main>
      <h2 className="text-xl font-semibold mb-4">
        Upload Claim
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium">
            Member Code
          </label>
          <input
            value={member}
            onChange={(e) => setMember(e.target.value)}
            placeholder="Enter member code"
            className="mt-1 p-2 border rounded w-full"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium">
            Amount
          </label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="Enter claim amount"
            className="mt-1 p-2 border rounded w-full"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium">
            Prescription
          </label>
          <input
            type="file"
            onChange={(e) =>
              setPrescriptionFile(
                e.target.files?.[0] || null
              )
            }
            className="mt-1"
          />
        </div>

        <div>
          <label className="block text-sm font-medium">
            Bill
          </label>
          <input
            type="file"
            onChange={(e) =>
              setBillFile(e.target.files?.[0] || null)
            }
            className="mt-1"
          />
        </div>

        <div>
          <label className="block text-sm font-medium">
            Report
          </label>
          <input
            type="file"
            onChange={(e) =>
              setReportFile(e.target.files?.[0] || null)
            }
            className="mt-1"
          />
        </div>

        <div>
          <button className="px-4 py-2 bg-green-600 text-white rounded">
            Submit Claim
          </button>
        </div>
      </form>

      <pre className="mt-4 bg-white p-4 rounded overflow-auto">
        {message}
      </pre>
    </main>
  )
}
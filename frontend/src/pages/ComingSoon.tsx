import { Layout } from '../components/Layout'

export function ComingSoon({ label, phase }: { label: string; phase: number }) {
  return (
    <Layout>
      <div className="px-8 py-6">
        <h2 className="text-xl font-semibold text-slate-50">{label}</h2>
        <div className="panel p-6 mt-6 text-sm text-slate-500 max-w-lg">
          <strong className="text-slate-400">Not implemented yet.</strong> {label} is built in Phase {phase} of
          the project plan.
        </div>
      </div>
    </Layout>
  )
}

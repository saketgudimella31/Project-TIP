import { createFileRoute } from '@tanstack/react-router'
import { RequirementsPanel } from './requirements'

export const Route = createFileRoute('/repositories')({
  validateSearch: (search: Record<string, unknown>): { task?: string } => ({
    task: typeof search.task === 'string' ? search.task : undefined,
  }),
  component: Repositories,
})

function Repositories() {
  const { task } = Route.useSearch()
  const navigate = Route.useNavigate()
  return <RequirementsPanel
    taskId={task}
    onTaskChange={(taskId) => navigate({ search: { task: taskId } })}
  />
}
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { platformApi, type ProjectMemory, type SearchMode } from '../lib/platform-api'
import { errorMessage } from '../lib/requirements-api'
import { Button } from './ui/button'
import { Input } from './ui/input'
import { Label } from './ui/label'
import { Select } from './ui/select'
import { Textarea } from './ui/textarea'

export function KnowledgePanel({ projectId, mode }: { projectId: string; mode: SearchMode }) {
  const [question, setQuestion] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [type, setType] = useState<ProjectMemory['memory_type']>('note')
  const [session, setSession] = useState<string>()
  const client = useQueryClient()
  const search = useMutation({ mutationFn: () => platformApi.search(projectId, question, mode) })
  const answer = useMutation({
    mutationFn: () => platformApi.answer(projectId, question, mode, session),
    onSuccess: (result) => setSession(result.session_id),
  })
  const memories = useQuery({
    queryKey: ['project-memories', projectId],
    queryFn: () => platformApi.memories(projectId),
    enabled: Boolean(projectId),
  })
  const save = useMutation({
    mutationFn: () => platformApi.addMemory(projectId, title, content, type),
    onSuccess: async () => {
      setTitle('')
      setContent('')
      await client.invalidateQueries({ queryKey: ['project-memories', projectId] })
    },
  })
  const remove = useMutation({
    mutationFn: (id: string) => platformApi.deleteMemory(id),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['project-memories', projectId] })
    },
  })
  return <section className="space-y-3" aria-label="Knowledge and project memory">
    <h3 className="font-semibold">Knowledge search &amp; project memory</h3>
    <Label htmlFor="knowledge-question">Question or vector search query</Label>
    <Input id="knowledge-question" value={question} onChange={(event) => setQuestion(event.target.value)} />
    <div className="flex flex-wrap gap-3">
      <Button type="button" disabled={!projectId || !question.trim() || search.isPending}
        onClick={() => search.mutate()}>Search knowledge chunks</Button>
      <Button type="button" disabled={!projectId || !question.trim() || answer.isPending}
        onClick={() => answer.mutate()}>Ask model with citations</Button>
    </div>
    {search.isError && <p role="alert">{errorMessage(search.error)}</p>}
    {answer.isError && <p role="alert">{errorMessage(answer.error)}</p>}
    {search.data && <div>
      <p>{search.data.semantic ? 'Semantic embeddings' : 'Local token-hash embeddings (not semantic)'} / {search.data.nodes.length} chunks</p>
      {search.data.nodes.map((node) => <details key={node.id}>
        <summary>{node.ref} / score {node.score.toFixed(4)}</summary>
        <pre className="whitespace-pre-wrap text-xs">{node.text}</pre>
      </details>)}
    </div>}
    {answer.data && <div role="status">
      <p>{answer.data.answer}</p>
      <p className="break-all text-xs">Source chunk citations: {answer.data.citations.join(', ')}</p>
    </div>}
    <form className="space-y-2" onSubmit={(event) => { event.preventDefault(); save.mutate() }}>
      <Label htmlFor="memory-title">Memory title</Label>
      <Input id="memory-title" required value={title} onChange={(event) => setTitle(event.target.value)} />
      <Label htmlFor="memory-type">Memory type</Label>
      <Select id="memory-type" value={type} onChange={(event) => {
        const selected = event.target.value
        if (selected === 'note' || selected === 'decision' || selected === 'preference'
          || selected === 'experience' || selected === 'convention' || selected === 'plan') setType(selected)
      }}>
        {['note', 'decision', 'preference', 'experience', 'convention', 'plan'].map((value) => (
          <option value={value} key={value}>{value}</option>
        ))}
      </Select>
      <Label htmlFor="memory-content">Memory content (do not enter secrets)</Label>
      <Textarea id="memory-content" required value={content} onChange={(event) => setContent(event.target.value)} />
      <Button type="submit" disabled={!projectId || save.isPending}>Save project memory</Button>
    </form>
    {save.isError && <p role="alert">{errorMessage(save.error)}</p>}
    {remove.isError && <p role="alert">{errorMessage(remove.error)}</p>}
    {memories.isError && <p role="alert">{errorMessage(memories.error)}</p>}
    {memories.data?.memories.map((memory) => <article className="rounded border p-3" key={memory.id}>
      <h4>{memory.title} ({memory.memory_type})</h4>
      <p>{memory.content}</p>
      <Button type="button" variant="outline" disabled={remove.isPending}
        onClick={() => remove.mutate(memory.id)}>Delete memory: {memory.title}</Button>
    </article>)}
  </section>
}
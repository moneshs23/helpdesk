import { useCallback, useEffect, useRef, useState } from "react";
import {
  UploadCloud,
  FileText,
  Trash2,
  Pin,
  PinOff,
  Eye,
  Search,
  RefreshCw,
} from "lucide-react";
import { api } from "../lib/api";
import type { DocumentMetadata } from "../lib/types";
import { Button, Card, Badge, Spinner, EmptyState } from "../components/ui";
import { useToast } from "../context/ToastContext";

export default function UploadPage() {
  const { push } = useToast();
  const [docs, setDocs] = useState<DocumentMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [query, setQuery] = useState("");
  const [product, setProduct] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .listDocuments(query ? { query } : undefined)
      .then((d) => setDocs(d.documents))
      .finally(() => setLoading(false));
  }, [query]);

  useEffect(() => {
    load();
  }, [load]);

  // While any document is still ingesting, poll so chunk counts/status update live.
  useEffect(() => {
    if (!docs.some((d) => d.status === "processing" || d.status === "pending")) return;
    const t = setInterval(() => {
      api
        .listDocuments(query ? { query } : undefined)
        .then((d) => setDocs(d.documents))
        .catch(() => {});
    }, 2500);
    return () => clearInterval(t);
  }, [docs, query]);

  const uploadFiles = async (files: FileList | File[]) => {
    setUploading(true);
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      if (product) form.append("product", product);
      try {
        const res = await api.upload(form);
        push(
          res.document.status === "processing"
            ? `${res.document.filename}: processing in background...`
            : `${res.document.filename}: ${res.document.chunk_count} chunks`,
          "success"
        );
      } catch (e: any) {
        push(e?.response?.data?.detail || `Failed: ${file.name}`, "error");
      }
    }
    setUploading(false);
    load();
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  };

  const remove = async (id: string) => {
    if (!confirm("Delete this document and its embeddings?")) return;
    try {
      await api.deleteDocument(id);
      push("Document deleted", "success");
    } catch (e: any) {
      push(e?.response?.data?.detail || "Delete failed", "error");
    }
    load();
  };

  const togglePin = async (d: DocumentMetadata) => {
    await api.updateDocument(d.id, { pinned: !d.pinned });
    load();
  };

  return (
    <div className="space-y-6 animate-pop-in">
      <h1 className="font-display text-3xl font-bold">Upload Documents</h1>

      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`brutal-card-lg flex cursor-pointer flex-col items-center justify-center gap-3 py-14 text-center transition-colors ${
            dragOver ? "border-brutal-blue bg-blue-50 dark:bg-blue-950/20" : "bg-white dark:bg-brutal-darkcard"
          }`}
        >
          <div className="flex h-16 w-16 items-center justify-center rounded-brutal border border-brutal-border bg-brutal-blue text-white dark:border-brutal-borderDark">
            <UploadCloud size={30} />
          </div>
          <p className="font-display text-xl font-bold">Drag & drop files here</p>
          <p className="text-sm opacity-70">
            or click to browse — PDF, Word, PowerPoint, Excel, CSV, Markdown, HTML, JSON, XML, RTF, TXT
          </p>
          {uploading && <Spinner label="Uploading..." />}
          <input
            ref={inputRef}
            type="file"
            multiple
            hidden
            accept=".pdf,.docx,.doc,.txt,.text,.csv,.tsv,.xlsx,.xls,.xlsm,.md,.markdown,.pptx,.html,.htm,.json,.xml,.rtf,.log,.yaml,.yml,.ini,.rst"
            onChange={(e) => e.target.files && uploadFiles(e.target.files)}
          />
        </div>

        {/* Options */}
        <Card className="h-fit">
          <h2 className="mb-2 font-display font-bold">Tag on upload</h2>
          <label className="mb-1 block text-xs font-bold opacity-70">Product</label>
          <input className="brutal-input" placeholder="e.g. AcmeCool 3000" value={product} onChange={(e) => setProduct(e.target.value)} />
          <p className="mt-2 text-xs opacity-60">New uploads will be tagged with this product for filtered search.</p>
        </Card>
      </div>

      {/* Search + list */}
      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-lg font-bold">Documents ({docs.length})</h2>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 brutal-input !w-auto !py-1">
              <Search size={14} />
              <input
                className="bg-transparent outline-none"
                placeholder="Search..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <Button variant="ghost" onClick={load} className="!py-1">
              <RefreshCw size={14} />
            </Button>
          </div>
        </div>

        {loading ? (
          <Spinner />
        ) : docs.length === 0 ? (
          <EmptyState icon={<FileText size={40} />} title="No documents yet" hint="Upload company docs to power the assistant." />
        ) : (
          <div className="space-y-2">
            {docs.map((d) => (
              <div
                key={d.id}
                className="flex flex-wrap items-center gap-3 rounded-brutal border border-brutal-border p-3 dark:border-brutal-borderDark"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-brutal border border-brutal-border bg-brutal-yellow text-xs font-bold uppercase dark:border-brutal-borderDark">
                  {d.doc_type}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold">{d.title}</p>
                  <p className="truncate text-xs opacity-60">
                    {d.filename} · {(d.size_bytes / 1024).toFixed(0)} KB · v{d.version} ·{" "}
                    {new Date(d.upload_date).toLocaleDateString()}
                  </p>
                </div>
                <Badge color={d.status === "ready" ? "green" : d.status === "failed" ? "red" : "yellow"}>
                  {d.status === "failed"
                    ? `failed${d.error ? `: ${d.error.slice(0, 60)}` : ""}`
                    : d.status === "ready"
                      ? `${d.chunk_count} chunks · ${d.pages}p`
                      : `processing... ${d.chunk_count} chunks`}
                </Badge>
                <div className="flex items-center gap-1">
                  <button className="brutal-btn-ghost !px-2 !py-1" title="Pin" onClick={() => togglePin(d)}>
                    {d.pinned ? <Pin size={14} /> : <PinOff size={14} />}
                  </button>
                  {d.doc_type === "pdf" && (
                    <a className="brutal-btn-ghost !px-2 !py-1" href={api.previewUrl(d.id)} target="_blank" rel="noreferrer" title="Preview">
                      <Eye size={14} />
                    </a>
                  )}
                  <button className="brutal-btn-pink !px-2 !py-1" title="Delete" onClick={() => remove(d.id)}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

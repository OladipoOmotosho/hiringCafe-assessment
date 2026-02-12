import { useMemo, useState } from "react";
import { refineJobs, searchJobs } from "./api";

function toPlainText(value) {
    if (!value) {
        return "";
    }
    const parser = new DOMParser();
    const document = parser.parseFromString(String(value), "text/html");
    return (document.body.textContent || "").replace(/\s+/g, " ").trim();
}

export default function App() {
    const [query, setQuery] = useState("");
    const [context, setContext] = useState(null);
    const [results, setResults] = useState([]);
    const [suggestions, setSuggestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const canSubmit = useMemo(() => query.trim().length > 0 && !loading, [query, loading]);

    async function onSubmit() {
        if (!query.trim()) {
            return;
        }
        setLoading(true);
        setError("");
        try {
            const response = context
                ? await refineJobs(query.trim(), context, 20)
                : await searchJobs(query.trim(), 20);
            setContext(response.context);
            setResults(response.results || []);
            setSuggestions(response.suggestions || []);
            setQuery("");
        } catch (submitError) {
            setError(submitError?.message || "Request failed");
        } finally {
            setLoading(false);
        }
    }

    async function onSuggestionClick(text) {
        setQuery(text);
        setLoading(true);
        setError("");
        try {
            const response = context
                ? await refineJobs(text, context, 20)
                : await searchJobs(text, 20);
            setContext(response.context);
            setResults(response.results || []);
            setSuggestions(response.suggestions || []);
            setQuery("");
        } catch (submitError) {
            setError(submitError?.message || "Request failed");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="min-h-screen bg-neutral-50 text-neutral-900">
            <div className="max-w-5xl mx-auto px-4 py-8">
                <h1 className="text-2xl font-semibold">AI Job Discovery</h1>
                <p className="text-sm text-neutral-600 mt-2">
                    Search jobs with natural language and refine results conversationally.
                </p>

                <div className="mt-6 bg-surface p-4 rounded-lg shadow-sm border border-neutral-200">
                    <div className="flex flex-col md:flex-row gap-3">
                        <input
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            onKeyDown={(event) => {
                                if (event.key === "Enter" && canSubmit) {
                                    onSubmit();
                                }
                            }}
                            placeholder={context ? "Refine your previous results..." : "Search jobs..."}
                            className="flex-1 rounded-md border border-neutral-300 bg-neutral-0 px-3 py-2 text-sm outline-none focus:border-brand-500"
                        />
                        <button
                            onClick={onSubmit}
                            disabled={!canSubmit}
                            className="rounded-md bg-brand-600 text-neutral-0 px-4 py-2 text-sm font-medium disabled:opacity-50"
                        >
                            {loading ? "Searching..." : context ? "Refine" : "Search"}
                        </button>
                    </div>
                    {context?.history?.length ? (
                        <div className="mt-3 text-xs text-neutral-600">
                            Conversation: {context.history.join(" → ")}
                        </div>
                    ) : null}
                    {error ? <div className="mt-3 text-sm text-error">{error}</div> : null}
                </div>

                {suggestions.length > 0 ? (
                    <div className="mt-6">
                        <h2 className="text-sm font-medium text-neutral-800">Suggestions</h2>
                        <div className="mt-2 flex flex-wrap gap-2">
                            {suggestions.map((item) => (
                                <button
                                    key={`${item.text}-${item.reason}`}
                                    onClick={() => onSuggestionClick(item.text)}
                                    disabled={loading}
                                    className="rounded-full border border-neutral-300 bg-neutral-0 px-3 py-1 text-xs text-neutral-700 hover:border-brand-500 disabled:opacity-50"
                                >
                                    {item.text}
                                </button>
                            ))}
                        </div>
                    </div>
                ) : null}

                <div className="mt-6 grid gap-3">
                    {results.map((job) => (
                        <article
                            key={job.id}
                            className="bg-surface rounded-lg border border-neutral-200 p-4 shadow-sm"
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <h3 className="font-semibold text-neutral-900">{job.title}</h3>
                                    <p className="text-sm text-neutral-600 mt-1">
                                        {job.company} · {job.location}
                                    </p>
                                </div>
                                <span className="text-xs text-neutral-600">score {job.score}</span>
                            </div>
                            <p className="text-sm text-neutral-700 mt-3">{toPlainText(job.preview)}</p>
                            {job.matched_signals?.length ? (
                                <div className="mt-3 text-xs text-neutral-600">
                                    matched: {job.matched_signals.join(", ")}
                                </div>
                            ) : null}
                            <a
                                href={job.apply_url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-block mt-3 text-sm text-brand-700"
                            >
                                Apply
                            </a>
                        </article>
                    ))}
                </div>
            </div>
        </div>
    );
}

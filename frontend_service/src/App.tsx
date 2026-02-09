import React, { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Code, MessageSquare, Database, Share2 } from "lucide-react";

const App = () => {
  const [query, setQuery] = useState("");
  const [guildId, setGuildId] = useState("");
  const [messageLimit, setMessageLimit] = useState(100);
  const [loading, setLoading] = useState(false);
  const [scraping, setScraping] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const modalUrl = import.meta.env.VITE_MODAL_URL;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${modalUrl}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      });

      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const DataFlowStep = ({ title, description, icon: Icon, children }) => (
    <Card className="mb-4">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5" />
          <CardTitle className="text-lg">{title}</CardTitle>
        </div>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );

  const MessageHistory = ({ messages }) => (
    <ScrollArea className="h-96">
      <div className="space-y-4">
        {messages?.map((message, idx) => (
          <div key={idx} className="rounded-lg bg-muted p-4">
            <div className="font-semibold mb-2">{message.role}</div>
            <div className="whitespace-pre-wrap">{message.content}</div>
            {message.tool_calls && (
              <div className="mt-2 p-2 bg-secondary rounded">
                <div className="font-semibold">Tool Call:</div>
                <div>{message.tool_calls[0].function.name}</div>
                <div className="font-mono text-sm mt-1">
                  {message.tool_calls[0].function.arguments}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </ScrollArea>
  );

  return (
    <div className="container mx-auto py-6 max-w-4xl">
      <h1 className="text-3xl font-bold mb-6">RAG Pipeline Visualizer</h1>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Discord Server Scraper</CardTitle>
          <CardDescription>
            Configure and initiate Discord server data scraping
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setScraping(true);
              try {
                const response = await fetch(
                  `${modalUrl}/discord/${guildId}?limit=${messageLimit}`,
                  { method: "POST" },
                );
                const data = await response.json();
                if (!response.ok)
                  throw new Error(data.error || "Failed to scrape server");
                alert("Server scraped successfully!");
              } catch (err) {
                setError(err.message);
              } finally {
                setScraping(false);
              }
            }}
            className="flex gap-4"
          >
            <Input
              value={guildId}
              onChange={(e) => setGuildId(e.target.value)}
              placeholder="Discord Server ID"
              className="flex-1"
            />
            <Input
              type="number"
              value={messageLimit}
              onChange={(e) => setMessageLimit(e.target.value)}
              placeholder="Message Limit"
              className="w-32"
            />
            <Button type="submit" disabled={scraping}>
              {scraping ? "Scraping..." : "Scrape Server"}
            </Button>
          </form>
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about the Discord data..."
            className="flex-1"
          />
          <Button type="submit" disabled={loading}>
            {loading ? "Processing..." : "Submit"}
          </Button>
        </div>
      </form>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && (
        <div className="space-y-6">
          <Card className="border-2 border-primary">
            <CardHeader>
              <CardTitle className="text-xl">Final Answer</CardTitle>
              <CardDescription>
                The system's response to your query
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-muted p-4 rounded-lg whitespace-pre-wrap">
                {result.answer}
              </div>
            </CardContent>
          </Card>
          <DataFlowStep
            title="1. Query Analysis"
            description="The system analyzes your query to determine the best approach (RAG or SQL)"
            icon={MessageSquare}
          >
            <div className="font-mono text-sm bg-muted p-4 rounded">
              Query: {query}
            </div>
          </DataFlowStep>

          <DataFlowStep
            title="2. Processing Approach"
            description="Based on the query, the system chose either RAG or SQL processing"
            icon={Share2}
          >
            <div className="bg-muted p-4 rounded">
              <span className="font-semibold">Selected Approach: </span>
              {result.chat_history
                .find((m) => m.tool_calls)
                ?.tool_calls[0]?.function?.arguments.includes(
                  '"approach":"sql"',
                )
                ? "SQL Query Generation"
                : "RAG Similarity Search"}
            </div>
          </DataFlowStep>

          {result.chat_history
            .find((m) => m.tool_calls)
            ?.tool_calls[0]?.function?.arguments.includes(
              '"approach":"sql"',
            ) && (
            <DataFlowStep
              title="3. Generated SQL"
              description="The SQL query generated to answer your question"
              icon={Database}
            >
              <pre className="bg-muted p-4 rounded overflow-x-auto">
                <code>
                  {
                    JSON.parse(
                      result.chat_history.find((m) => m.tool_calls)
                        ?.tool_calls[0]?.function?.arguments || "{}",
                    ).sql_query
                  }
                </code>
              </pre>
            </DataFlowStep>
          )}

          <DataFlowStep
            title="4. Complete Interaction Flow"
            description="The full conversation and data flow between components"
            icon={Code}
          >
            <Tabs defaultValue="messages">
              <TabsList>
                <TabsTrigger value="messages">Message History</TabsTrigger>
                <TabsTrigger value="raw">Raw Response</TabsTrigger>
              </TabsList>
              <TabsContent value="messages">
                <MessageHistory messages={result.chat_history} />
              </TabsContent>
              <TabsContent value="raw">
                <ScrollArea className="h-96">
                  <pre className="bg-muted p-4 rounded text-sm">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </DataFlowStep>
        </div>
      )}
    </div>
  );
};

export default App;
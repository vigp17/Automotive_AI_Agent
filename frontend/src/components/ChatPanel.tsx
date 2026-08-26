import { FormEvent, useEffect, useRef, useState } from "react";
import { sendChat, sendVoice } from "../api";

interface Message {
  role: "user" | "assistant";
  text: string;
  intent?: string;
}

const SUGGESTIONS = [
  "Get me to my next meeting",
  "Do I have enough battery for the airport?",
  "Set temperature to 22",
  "What's on my calendar?",
];

export default function ChatPanel({ sessionId }: { sessionId: string }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: "Hi, I'm your cabin copilot. I handle navigation, charging, climate and your calendar.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (text: string) => {
    if (!text.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const resp = await sendChat(text, sessionId);
      setMessages((m) => [...m, { role: "assistant", text: resp.reply, intent: resp.intent }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Sorry, something went wrong." }]);
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void ask(input);
  };

  const toggleMic = async () => {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        setBusy(true);
        try {
          const blob = new Blob(chunks, { type: recorder.mimeType });
          const resp = await sendVoice(blob, sessionId);
          setMessages((m) => [
            ...m,
            { role: "user", text: resp.transcript || "(voice)" },
            { role: "assistant", text: resp.reply, intent: resp.intent },
          ]);
          if (resp.audio_base64) {
            const audio = new Audio(`data:audio/wav;base64,${resp.audio_base64}`);
            void audio.play().catch(() => undefined);
          }
        } catch {
          setMessages((m) => [...m, { role: "assistant", text: "Voice request failed." }]);
        } finally {
          setBusy(false);
        }
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "Microphone unavailable - check browser permissions." },
      ]);
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`bubble ${msg.role}`}>
            {msg.intent && <span className="intent-tag">{msg.intent}</span>}
            <div className="bubble-text">{msg.text}</div>
          </div>
        ))}
        {busy && <div className="bubble assistant thinking">...</div>}
        <div ref={bottomRef} />
      </div>
      <div className="suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => void ask(s)} disabled={busy}>
            {s}
          </button>
        ))}
      </div>
      <form className="chat-input" onSubmit={onSubmit}>
        <button
          type="button"
          className={`mic-btn ${recording ? "recording" : ""}`}
          onClick={() => void toggleMic()}
          title={recording ? "Stop recording" : "Speak"}
        >
          {recording ? "◼" : "🎙"}
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your copilot..."
          disabled={busy}
        />
        <button type="submit" className="send-btn" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

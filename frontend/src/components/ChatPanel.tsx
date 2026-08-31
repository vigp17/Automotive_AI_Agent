import { FormEvent, useEffect, useRef, useState } from "react";
import { sendChat, sendVoice } from "../api";
import { getRecognizerCtor, RecognizerLike, speak } from "../speech";

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

export default function ChatPanel({
  sessionId,
  queuedPrompt,
  onQueuedPromptHandled,
}: {
  sessionId: string;
  queuedPrompt?: string | null;
  onQueuedPromptHandled?: () => void;
}) {
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
  const recognizerRef = useRef<RecognizerLike | null>(null);
  // Tracks which capture pipeline is live so start/stop clicks and async
  // recognition callbacks can't race each other into duplicate recorders.
  const modeRef = useRef<"idle" | "recognition" | "recorder">("idle");
  // Set when browser recognition errors out, so we stop retrying it and use
  // the server /voice pipeline instead.
  const recognitionBrokenRef = useRef(false);
  const fallbackAnnouncedRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (text: string, speakReply = false) => {
    if (!text.trim() || busy) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const resp = await sendChat(text, sessionId);
      setMessages((m) => [...m, { role: "assistant", text: resp.reply, intent: resp.intent }]);
      if (speakReply) speak(resp.reply);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Sorry, something went wrong." }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!queuedPrompt || busy) return;
    void ask(queuedPrompt);
    onQueuedPromptHandled?.();
  }, [queuedPrompt, busy]);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void ask(input);
  };

  const startRecognition = (): boolean => {
    const Ctor = getRecognizerCtor();
    if (!Ctor || recognitionBrokenRef.current) return false;

    const recognizer = new Ctor();
    recognizer.lang = "en-US";
    recognizer.interimResults = false;
    recognizer.maxAlternatives = 1;

    recognizer.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript ?? "";
      if (transcript.trim()) void ask(transcript, true);
    };
    recognizer.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setMessages((m) => [
          ...m,
          { role: "assistant", text: "Microphone access was denied - allow it in your browser and try again." },
        ]);
      } else if (event.error !== "no-speech" && event.error !== "aborted") {
        // e.g. "network": recognition service unavailable in this browser.
        // Fall back to the server /voice pipeline from now on.
        recognitionBrokenRef.current = true;
        if (!fallbackAnnouncedRef.current) {
          fallbackAnnouncedRef.current = true;
          setMessages((m) => [
            ...m,
            {
              role: "assistant",
              text: "(Browser speech recognition isn't available here - switching to the onboard voice pipeline. Click the mic, speak, then click again to stop.)",
            },
          ]);
        }
        void recordAndSend();
      }
    };
    recognizer.onend = () => {
      recognizerRef.current = null;
      // Only clear the UI if we didn't hand off to the recorder fallback.
      if (modeRef.current === "recognition") {
        modeRef.current = "idle";
        setRecording(false);
      }
    };

    recognizerRef.current = recognizer;
    modeRef.current = "recognition";
    recognizer.start();
    setRecording(true);
    return true;
  };

  const recordAndSend = async () => {
    if (modeRef.current === "recorder") return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        recorderRef.current = null;
        modeRef.current = "idle";
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
          } else {
            // Server did TTS-less transcription (local Whisper): speak the
            // reply with the browser's own voice.
            speak(resp.reply);
          }
        } catch {
          setMessages((m) => [...m, { role: "assistant", text: "Voice request failed." }]);
        } finally {
          setBusy(false);
        }
      };
      recorderRef.current = recorder;
      modeRef.current = "recorder";
      recorder.start();
      setRecording(true);
    } catch (err) {
      modeRef.current = "idle";
      setRecording(false);
      const detail = err instanceof Error ? ` (${err.name})` : "";
      setMessages((m) => [
        ...m,
        { role: "assistant", text: `Microphone unavailable${detail} - check browser permissions.` },
      ]);
    }
  };

  const stopCapture = () => {
    if (modeRef.current === "recognition") recognizerRef.current?.stop();
    else if (modeRef.current === "recorder") recorderRef.current?.stop();
  };

  const startCapture = async () => {
    // Prefer browser-native speech recognition (real STT, no server keys);
    // fall back to recording + server /voice (local Whisper, Azure, or mock).
    if (!startRecognition()) {
      await recordAndSend();
    }
  };

  // Hold-to-talk with tap-to-toggle fallback: pressing starts capture; a
  // release after >350 ms stops it (hold gesture), while a quick tap leaves
  // it running so a second tap can stop it.
  const HOLD_THRESHOLD_MS = 350;
  const pressRef = useRef<{ startedCapture: boolean; at: number } | null>(null);

  const onMicDown = async () => {
    if (modeRef.current === "idle") {
      pressRef.current = { startedCapture: true, at: Date.now() };
      await startCapture();
    } else {
      pressRef.current = { startedCapture: false, at: Date.now() };
    }
  };

  const onMicUp = () => {
    const press = pressRef.current;
    pressRef.current = null;
    if (!press) return;
    if (!press.startedCapture || Date.now() - press.at > HOLD_THRESHOLD_MS) {
      stopCapture();
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
          onPointerDown={() => void onMicDown()}
          onPointerUp={onMicUp}
          onPointerCancel={onMicUp}
          onContextMenu={(e) => e.preventDefault()}
          title={recording ? "Release or tap to stop" : "Hold to talk (or tap to toggle)"}
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

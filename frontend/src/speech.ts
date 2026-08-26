// Browser-native speech: Web Speech API recognition (real STT with no server
// keys) and speechSynthesis for spoken replies. The server /voice pipeline
// (Azure or mock) is used as fallback when recognition is unavailable.

export interface RecognizerLike {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export interface RecognitionEvent {
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
}

export interface RecognitionErrorEvent {
  error: string;
}

type RecognizerCtor = new () => RecognizerLike;

export function getRecognizerCtor(): RecognizerCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: RecognizerCtor;
    webkitSpeechRecognition?: RecognizerCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function speak(text: string): void {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 1.05;
  window.speechSynthesis.speak(utterance);
}

/**
 * Dictation, using the browser's own speech recognition.
 *
 * Nothing is uploaded by us and no second API key is needed: the browser does
 * the transcription and hands back text, which then travels the same path a
 * typed question would. Support is uneven — Chrome and Edge have it, Firefox
 * does not — so `isSpeechSupported` gates the microphone button rather than
 * offering one that quietly does nothing.
 */

interface SpeechRecognitionAlternative {
  transcript: string;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  0: SpeechRecognitionAlternative;
}

interface SpeechRecognitionEvent {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: SpeechRecognitionResult;
  };
}

interface SpeechRecognitionErrorEvent {
  error: string;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function getConstructor(): SpeechRecognitionConstructor | undefined {
  const scope = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition;
}

export const isSpeechSupported = !!getConstructor();

export interface DictationHandlers {
  /** Fires as the user speaks, with the best guess so far. */
  onInterim?: (text: string) => void;
  /** Fires once per settled phrase. */
  onFinal: (text: string) => void;
  onError?: (message: string) => void;
  onEnd?: () => void;
}

export interface Dictation {
  stop(): void;
}

/**
 * Starts listening. Returns a handle whose `stop` ends the session; the
 * browser also ends it on its own after a pause, which is what `onEnd` is for.
 */
export function startDictation(
  language: string,
  handlers: DictationHandlers
): Dictation {
  const Recognition = getConstructor();
  if (!Recognition) {
    handlers.onError?.('speech recognition is not available in this browser');
    handlers.onEnd?.();
    return { stop: () => undefined };
  }

  const recognition = new Recognition();
  recognition.lang = language;
  // Keep listening through natural pauses — an accounting question often has
  // one in the middle of it.
  recognition.continuous = true;
  recognition.interimResults = true;

  recognition.onresult = (event) => {
    let interim = '';

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const transcript = result[0].transcript;

      if (result.isFinal) {
        handlers.onFinal(transcript.trim());
      } else {
        interim += transcript;
      }
    }

    if (interim) {
      handlers.onInterim?.(interim.trim());
    }
  };

  recognition.onerror = (event) => {
    // `no-speech` and `aborted` are how a normal session ends when someone
    // says nothing or presses stop; surfacing them as failures would be noise.
    if (event.error === 'no-speech' || event.error === 'aborted') {
      return;
    }

    handlers.onError?.(
      event.error === 'not-allowed'
        ? 'microphone access was denied'
        : `dictation failed: ${event.error}`
    );
  };

  recognition.onend = () => handlers.onEnd?.();

  try {
    recognition.start();
  } catch (err) {
    handlers.onError?.((err as Error).message);
    handlers.onEnd?.();
  }

  return { stop: () => recognition.stop() };
}

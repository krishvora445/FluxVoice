import { WhisperPill } from "./components/WhisperPill";
import { useFluxVoiceState } from "./lib/ws";

function App() {
  const { state, isConnected } = useFluxVoiceState();

  return (
    <main className="flex h-full w-full items-center justify-center bg-transparent">
      <WhisperPill state={state} isConnected={isConnected} />
    </main>
  );
}

export default App;


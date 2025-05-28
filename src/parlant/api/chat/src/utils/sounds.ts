/* eslint-disable @typescript-eslint/no-explicit-any */
function soundDoubleBlip(reversed?: boolean) {
  const AudioCtx = window.AudioContext || (window as any)['webkitAudioContext'];
  const ctx = new AudioCtx();

  const blip = (startTime: number, freq: number) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(freq, startTime);
    gain.gain.setValueAtTime(0.5, startTime);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.15);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(startTime);
    osc.stop(startTime + 0.15);
  };

  const now = ctx.currentTime;
  if (reversed) {
    blip(now, 660);
    blip(now + 0.2, 880);
    return;
  }
  blip(now, 880);
  blip(now + 0.2, 660);
}

export { soundDoubleBlip };
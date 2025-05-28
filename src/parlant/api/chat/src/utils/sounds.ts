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

function soundLayeredChime(reversed?: boolean) {
  const ctx = new (window.AudioContext || (window as any)['webkitAudioContext'])();

  const freqs = reversed ? [1320, 880] : [880, 1320];
  freqs.forEach((f, i) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(f, ctx.currentTime);
    gain.gain.setValueAtTime(0.4, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4 + i * 0.05);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(ctx.currentTime + i * 0.05);
    osc.stop(ctx.currentTime + 0.4 + i * 0.05);
  });
}

function soundBlipUp(reversed = false) {
  const ctx = new (window.AudioContext || (window as any)['webkitAudioContext'])();
  const now = ctx.currentTime;

  const blip = (t: number, f: number) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(f, t);
    gain.gain.setValueAtTime(0.4, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.15);
  };

  if (reversed) {
    blip(now, 990);
    blip(now + 0.18, 660);
  } else {
    blip(now, 660);
    blip(now + 0.18, 990);
  }
}

function soundChirpPop(reversed = false) {
  const ctx = new (window.AudioContext || (window as any)['webkitAudioContext'])();
  const now = ctx.currentTime;

  const blip = (t: number, f: number) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(f, t);
    gain.gain.setValueAtTime(0.35, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.12);
  };

  if (reversed) {
    blip(now, 495);
    blip(now + 0.14, 990);
  } else {
    blip(now, 990);
    blip(now + 0.14, 495);
  }
}

function soundSoftBounce(reversed = false) {
  const ctx = new (window.AudioContext || (window as any)['webkitAudioContext'])();
  const now = ctx.currentTime;

  const blip = (t: number, f: number) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(f, t);
    gain.gain.setValueAtTime(0.4, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.2);
  };

  if (reversed) {
    blip(now, 660);
    blip(now + 0.2, 770);
  } else {
    blip(now, 770);
    blip(now + 0.2, 660);
  }
}

function soundBlipCascade(reversed = false) {
  const ctx = new (window.AudioContext || (window as any)['webkitAudioContext'])();
  const now = ctx.currentTime;

  const blip = (t: number, f: number) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(f, t);
    gain.gain.setValueAtTime(0.3, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t);
    osc.stop(t + 0.12);
  };

  if (reversed) {
    blip(now, 660);
    blip(now + 0.15, 880);
    blip(now + 0.3, 1040);
  } else {
    blip(now, 1040);
    blip(now + 0.15, 880);
    blip(now + 0.3, 660);
  }
}



export { soundDoubleBlip, soundLayeredChime, soundBlipUp, soundChirpPop, soundSoftBounce, soundBlipCascade };
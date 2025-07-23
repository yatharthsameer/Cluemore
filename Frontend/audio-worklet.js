class PCMChunker extends AudioWorkletProcessor {
  constructor(opts) {
    super();
    this.targetSampleRate = 16000; // Target for Whisper
    this.sourceSampleRate = sampleRate; // Current audio context sample rate
    this.targetFrameSize = Math.floor(this.targetSampleRate * 0.02); // 20ms @ 16kHz = 320 samples
    this.sourceFrameSize = Math.floor(this.sourceSampleRate * 0.02); // 20ms @ source rate
    this.buf = new Float32Array(0);
    
    console.log(`AudioWorklet: Source rate ${this.sourceSampleRate}Hz, Target rate ${this.targetSampleRate}Hz`);
  }

  process(inputs) {
    const input = inputs[0][0];
    if (!input || input.length === 0) return true;

    // Concatenate new input with existing buffer
    const merged = new Float32Array(this.buf.length + input.length);
    merged.set(this.buf);
    merged.set(input, this.buf.length);

    let offset = 0;
    while (offset + this.sourceFrameSize <= merged.length) {
      const slice = merged.subarray(offset, offset + this.sourceFrameSize);
      
      // Downsample if needed (simple decimation)
      let processedSlice = slice;
      if (this.sourceSampleRate !== this.targetSampleRate) {
        const decimationFactor = Math.round(this.sourceSampleRate / this.targetSampleRate);
        const downsampledLength = Math.floor(slice.length / decimationFactor);
        processedSlice = new Float32Array(downsampledLength);
        for (let i = 0; i < downsampledLength; i++) {
          processedSlice[i] = slice[i * decimationFactor];
        }
      }
      
      // Convert to Int16 for WebSocket transmission
      const int16 = new Int16Array(processedSlice.length);
      for (let i = 0; i < processedSlice.length; i++) {
        const s = Math.max(-1, Math.min(1, processedSlice[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      
      // Only send if we have enough samples
      if (int16.length >= 160) { // Minimum 10ms @ 16kHz
        this.port.postMessage({ 
          pcm: int16, 
          sampleRate: this.targetSampleRate,
          originalSampleRate: this.sourceSampleRate,
          timestamp: currentTime 
        }, [int16.buffer]);
      }
      
      offset += this.sourceFrameSize;
    }
    
    // Keep remaining samples for next frame
    this.buf = merged.subarray(offset);
    return true;
  }
}

registerProcessor('pcm-chunker', PCMChunker); 
// Logarithmic position is independent of the displayed, rounded frequency.
export function createLowpassRange({high, track, onChange, minimum=.01, maximum=20, initial=2}) {
  let value = initial;
  function sync() {
    const position = 1000*Math.log(value/minimum)/Math.log(maximum/minimum);
    high.value = String(position);
    high.dataset.hz = String(value);
    high.dataset.maxHz = String(maximum);
    track.style.setProperty('--high-progress',`${position/10}%`);
    document.querySelector(`#${high.id}Value`).textContent = `${value.toFixed(2)} Hz`;
    document.querySelector(`#${high.id}Bpm`).textContent = `${(value*60).toFixed(2)} BPM`;
    high.setAttribute('aria-valuetext',`${value.toFixed(2)} Hz, ${(value*60).toFixed(2)} BPM`);
  }
  high.addEventListener('input',()=>{
    if (high.disabled) return;
    value = Math.min(maximum,Math.max(minimum,Number((minimum*Math.pow(maximum/minimum,Number(high.value)/1000)).toPrecision(3))));
    sync(); onChange?.(value);
  });
  let dragging = false;
  function move(event) {
    if (!dragging) return;
    const box = track.getBoundingClientRect();
    high.value = String(Math.round(Math.max(0,Math.min(1000,1000*(event.clientX-box.left-9)/(box.width-18)))));
    high.dispatchEvent(new Event('input',{bubbles:true}));
  }
  track.addEventListener('pointerdown',event=>{
    if (high.disabled || event.button !== 0) return;
    event.preventDefault(); dragging = true;
    high.focus({preventScroll:true}); track.setPointerCapture(event.pointerId); move(event);
  });
  track.addEventListener('pointermove',move);
  for (const type of ['pointerup','pointercancel','lostpointercapture']) track.addEventListener(type,()=>{dragging=false;});
  sync();
  return {value:()=>value, sync};
}

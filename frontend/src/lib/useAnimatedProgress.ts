import { onUnmounted, ref, watch, type Ref } from 'vue'

/**
 * Animates a displayed percentage toward the real, server-confirmed value.
 *
 * This never claims to be further along than the backend actually is: while
 * `active` (queued/processing), it only ever creeps up to a ceiling just
 * short of the next real checkpoint. What it fixes is the "stuck at 10% for
 * 6 seconds" dead feeling between polls - the same easing curve naturally
 * closes large gaps fast and small gaps slowly, so it reads as quick
 * progress early and a gentle settle near completion. Once no longer
 * active (done, or errored out short of 100), it snaps straight to the
 * real value - there's nothing left to visually smooth over.
 */
export function useAnimatedProgress(real: Ref<number>, active: Ref<boolean>): Ref<number> {
  const displayed = ref(real.value)
  let frame: number | null = null

  function stop() {
    if (frame !== null) {
      cancelAnimationFrame(frame)
      frame = null
    }
  }

  function tick() {
    if (!active.value) {
      displayed.value = real.value
      frame = null
      return
    }
    const ceiling = real.value >= 100 ? 100 : Math.min(real.value + 12, 96)
    const gap = ceiling - displayed.value
    displayed.value = Math.abs(gap) < 0.1 ? ceiling : displayed.value + gap * 0.045
    frame = requestAnimationFrame(tick)
  }

  watch(
    [real, active],
    () => {
      stop()
      if (active.value) {
        frame = requestAnimationFrame(tick)
      } else {
        displayed.value = real.value
      }
    },
    { immediate: true },
  )

  onUnmounted(stop)

  return displayed
}

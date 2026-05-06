<script setup>
import { Teleport, Transition } from 'vue'
import { useToastState } from '../composables/useToast'

const { visible, message, variant } = useToastState()
</script>

<template>
  <Teleport to="body">
    <Transition name="app-toast">
      <div
        v-if="visible"
        class="app-toast"
        :class="{
          'app-toast--success': variant === 'success',
          'app-toast--error': variant === 'error',
          'app-toast--info': variant === 'info',
        }"
        :role="variant === 'error' ? 'alert' : 'status'"
        :aria-live="variant === 'error' ? 'assertive' : 'polite'"
      >
        <span class="app-toast__text">{{ message }}</span>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.app-toast {
  position: fixed;
  left: 50%;
  top: calc(3.5rem + env(safe-area-inset-top, 0px));
  transform: translateX(-50%);
  z-index: 30000;
  display: flex;
  align-items: center;
  justify-content: center;
  max-width: min(92vw, 26rem);
  padding: 0.65rem 1rem;
  border-radius: 12px;
  font-size: 0.92rem;
  font-weight: 600;
  line-height: 1.45;
  box-shadow: 0 14px 38px -12px rgba(15, 23, 42, 0.45);
  pointer-events: none;
}

.app-toast__text {
  text-align: center;
  min-width: 0;
  word-break: break-word;
}

.app-toast--success {
  background: linear-gradient(135deg, #0d9488, #0f766e);
  color: #fff;
}

.app-toast--error {
  background: linear-gradient(135deg, #dc2626, #b91c1c);
  color: #fff;
}

.app-toast--info {
  background: linear-gradient(135deg, #475569, #334155);
  color: #f8fafc;
}

.app-toast-enter-active,
.app-toast-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}

.app-toast-enter-from,
.app-toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -8px);
}
</style>

import "@testing-library/jest-dom/vitest"

// Mock window.matchMedia if not available in jsdom
if (typeof window !== "undefined") {
  window.matchMedia =
    window.matchMedia ||
    function () {
      return {
        matches: false,
        addListener: function () {},
        removeListener: function () {},
        addEventListener: function () {},
        removeEventListener: function () {},
        dispatchEvent: function () {
          return true
        },
      }
    }

  // Mock HTMLDialogElement methods in jsdom
  if (typeof HTMLDialogElement !== "undefined") {
    HTMLDialogElement.prototype.showModal = function () {
      this.open = true
    }
    HTMLDialogElement.prototype.close = function () {
      this.open = false
    }
  }

  // Mock ResizeObserver
  ;(globalThis as any).ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
}

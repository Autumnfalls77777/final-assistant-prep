import { Icon } from "./Icon";

type WindowAction = "minimize" | "maximize" | "close";

async function runWindowAction(action: WindowAction): Promise<void> {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    const currentWindow = getCurrentWindow();
    if (action === "minimize") {
      await currentWindow.minimize();
    } else if (action === "maximize") {
      await currentWindow.toggleMaximize();
    } else {
      await currentWindow.close();
    }
  } catch {
    // Browser preview has no native window to control.
  }
}

export function WindowChrome() {
  return (
    <div className="window-chrome" aria-label="Window controls">
      <button
        type="button"
        className="window-chrome__button"
        onClick={() => void runWindowAction("minimize")}
        aria-label="Minimize window"
        title="Minimize"
      >
        <Icon name="minus" size={15} />
      </button>
      <button
        type="button"
        className="window-chrome__button"
        onClick={() => void runWindowAction("maximize")}
        aria-label="Maximize or restore window"
        title="Maximize"
      >
        <Icon name="square" size={12} />
      </button>
      <button
        type="button"
        className="window-chrome__button window-chrome__button--close"
        onClick={() => void runWindowAction("close")}
        aria-label="Close window"
        title="Close"
      >
        <Icon name="close" size={15} />
      </button>
    </div>
  );
}

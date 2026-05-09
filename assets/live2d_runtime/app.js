function modelUrlFromQuery() {
  const params = new URLSearchParams(window.location.search);
  return params.get("model") || "/live2d/model/model.model3.json";
}

const MODEL_SAFE_WIDTH = 0.9;
const MODEL_SAFE_HEIGHT = 0.92;
const MODEL_X = 0.52;
const MODEL_BOTTOM = 0.04;

async function main() {
  const motionPriority = PIXI.live2d?.MotionPriority || {};
  const tapMotionPriority = motionPriority.FORCE ?? 3;
  let lastTapMotionKey = "";

  const app = new PIXI.Application({
    view: document.getElementById("stage"),
    resizeTo: window,
    autoStart: true,
    transparent: true,
    antialias: true,
    backgroundAlpha: 0,
  });

  const model = await PIXI.live2d.Live2DModel.from(modelUrlFromQuery(), {
    autoInteract: false,
  });

  app.stage.addChild(model);

  function fitModel() {
    const bounds = model.getLocalBounds();
    console.info(
      `Live2D bounds x=${bounds.x.toFixed(1)} y=${bounds.y.toFixed(1)} ` +
      `w=${bounds.width.toFixed(1)} h=${bounds.height.toFixed(1)}`,
    );
    const scale = Math.min(
      (window.innerWidth * MODEL_SAFE_WIDTH) / bounds.width,
      (window.innerHeight * MODEL_SAFE_HEIGHT) / bounds.height,
    );

    model.scale.set(scale);
    model.anchor.set(0.5, 1.0);
    model.x = window.innerWidth * MODEL_X;
    model.y = window.innerHeight * (1 - MODEL_BOTTOM);
  }

  function playIdle() {
    try {
      model.motion("Idle", 0);
    } catch (error) {
      console.debug("Live2D idle motion failed", error);
    }
  }

  function tapMotionCandidates() {
    const motionManager = model.internalModel?.motionManager;
    const definitions = motionManager?.definitions || {};
    const idleGroup = motionManager?.groups?.idle || "Idle";
    return Object.entries(definitions).flatMap(([group, motions]) => {
      if (group === idleGroup || group.toLowerCase() === "idle" || !Array.isArray(motions)) {
        return [];
      }
      return motions.map((_motion, index) => ({ group, index }));
    });
  }

  function chooseTapMotion() {
    const candidates = tapMotionCandidates();
    if (!candidates.length) {
      return null;
    }

    const reusable = candidates.filter(
      (motion) => `${motion.group}:${motion.index}` !== lastTapMotionKey,
    );
    const pool = reusable.length ? reusable : candidates;
    return pool[Math.floor(Math.random() * pool.length)];
  }

  async function playTapMotion() {
    const tapMotion = chooseTapMotion();
    if (!tapMotion) {
      playIdle();
      return;
    }

    lastTapMotionKey = `${tapMotion.group}:${tapMotion.index}`;
    try {
      await model.expression();
      const started = await model.motion(tapMotion.group, tapMotion.index, tapMotionPriority);
      if (!started) {
        playIdle();
      }
    } catch (error) {
      console.debug("Live2D tap motion failed", error);
      playIdle();
    }
  }

  fitModel();
  window.addEventListener("resize", fitModel);
  playIdle();

  window.desktopMascot = {
    tap: playTapMotion,
    idle: playIdle,
  };

  document.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    window.desktopBridge?.contextMenu({
      x: event.screenX,
      y: event.screenY,
    });
  });

  document.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) {
      return;
    }
    window.desktopBridge?.pointerDown({
      x: event.screenX,
      y: event.screenY,
    });
  });

  document.addEventListener("pointermove", (event) => {
    if ((event.buttons & 1) === 0) {
      return;
    }
    window.desktopBridge?.pointerMove({
      x: event.screenX,
      y: event.screenY,
    });
  });

  document.addEventListener("pointerup", (event) => {
    if (event.button !== 0) {
      return;
    }
    window.desktopBridge?.pointerUp({
      x: event.screenX,
      y: event.screenY,
    });
  });

  window.desktopBridge?.onAction((action) => {
    if (action === "tap") {
      playTapMotion();
    } else if (action === "idle") {
      playIdle();
    }
  });

  console.info("Live2D loaded");
}

main().catch((error) => {
  console.error(error);
});

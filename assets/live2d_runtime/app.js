function modelUrlFromQuery() {
  const params = new URLSearchParams(window.location.search);
  return params.get("model") || "/live2d/model/model.model3.json";
}

async function main() {
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
      window.innerWidth / bounds.width,
      window.innerHeight / bounds.height,
    ) * 1.08;

    model.scale.set(scale);
    model.anchor.set(0.5, 1.0);
    model.x = window.innerWidth * 0.55;
    model.y = window.innerHeight * 0.99;
  }

  function playIdle() {
    try {
      model.motion("Idle", 0);
    } catch (error) {
      console.debug("Live2D idle motion failed", error);
    }
  }

  function playTapMotion() {
    playIdle();
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

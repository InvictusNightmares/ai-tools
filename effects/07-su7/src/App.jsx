import { Preloader } from "./ui/Preloader.jsx";
import { WebGLScene } from "./ui/WebGLScene.jsx";
import { SectionNavigation } from "./ui/Navigation.jsx";
import { SectionCopy } from "./ui/SectionCopy.jsx";
import { ColorBar } from "./ui/ColorBar.jsx";
import { SoundToggle } from "./ui/SoundToggle.jsx";
import { CustomPaintPanel } from "./ui/CustomPaintPanel.jsx";
import { PhotoButton } from "./ui/PhotoButton.jsx";
function App() {
  return (
    <>
      <Preloader />
      <WebGLScene />
      <SectionNavigation />
      <SectionCopy />
      <ColorBar />
      <SoundToggle />
      <CustomPaintPanel />
      <PhotoButton />
    </>
  );
}
export { App };

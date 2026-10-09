import "@fontsource/lora/600.css"
import "@fontsource/lora/700.css"
import "@fontsource/poppins/400.css"
import "@fontsource/poppins/500.css"
import "@fontsource/poppins/600.css"
import "@fontsource/ibm-plex-mono/500.css"
import { Composition } from "remotion"

import { TOTAL_FRAMES } from "./kit"
import { DocDuelPromo } from "./Video"

export const Root = () => (
  <>
    <Composition id="landscape" component={DocDuelPromo} durationInFrames={TOTAL_FRAMES} fps={30} width={1920} height={1080} />
    <Composition id="vertical" component={DocDuelPromo} durationInFrames={TOTAL_FRAMES} fps={30} width={1080} height={1920} />
  </>
)

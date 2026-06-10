import { loadFont as loadCormorant } from "@remotion/google-fonts/CormorantGaramond";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";

const cormorant = loadCormorant("normal", { weights: ["600", "700"] });
const inter = loadInter("normal", { weights: ["400", "500"] });

export const serifFamily = cormorant.fontFamily;
export const sansFamily = inter.fontFamily;

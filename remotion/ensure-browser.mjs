import {ensureBrowser} from "@remotion/renderer";

const status = await ensureBrowser({logLevel: "info"});
process.stdout.write(`${JSON.stringify(status)}\n`);

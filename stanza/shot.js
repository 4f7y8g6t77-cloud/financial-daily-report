const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({args:['--allow-file-access-from-files']});
  const p = await b.newPage({viewport:{width:1500,height:1860}, deviceScaleFactor: +(process.argv[2]||1)});
  await p.goto('file://' + __dirname + '/stanza.html');
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(400);
  await p.screenshot({path: __dirname + '/' + (process.argv[3]||'preview.png')});
  await b.close();
})();

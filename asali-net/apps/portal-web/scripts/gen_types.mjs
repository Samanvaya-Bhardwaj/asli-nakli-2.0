// Turns src/api/contract.schema.json (written by infra/scripts/gen_api_types.py) into src/api/generated.ts.
import { readFileSync, writeFileSync } from 'node:fs'
import { compile } from 'json-schema-to-typescript'

const schema = JSON.parse(readFileSync('src/api/contract.schema.json', 'utf8'))
const ts = await compile(schema, 'Contract', { additionalProperties: false, bannerComment: '// Generated from services/node/asali_node/contract.py. Do not edit: run npm run gen:types.', format: false, unreachableDefinitions: true })
writeFileSync('src/api/generated.ts', ts.replace(/\r\n/g, '\n'))
console.log('wrote src/api/generated.ts')

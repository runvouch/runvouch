import type {
	IDataObject,
	IExecuteFunctions,
	IHttpRequestMethods,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
	JsonObject,
} from 'n8n-workflow';
import { NodeApiError, NodeConnectionTypes, NodeOperationError } from 'n8n-workflow';

type Op = 'start' | 'end' | 'heartbeat';

async function runVouchRequest(
	ctx: IExecuteFunctions,
	method: IHttpRequestMethods,
	path: string,
	body?: IDataObject,
): Promise<IDataObject> {
	const credentials = await ctx.getCredentials('runVouchApi');
	const baseUrl = String(credentials.baseUrl || 'https://api.runvouch.com').replace(/\/+$/, '');
	return (await ctx.helpers.httpRequestWithAuthentication.call(ctx, 'runVouchApi', {
		method,
		url: `${baseUrl}${path}`,
		headers: { 'Content-Type': 'application/json', 'User-Agent': 'n8n-nodes-runvouch/0.1' },
		body,
		json: true,
	})) as IDataObject;
}

function isNotFound(error: unknown): boolean {
	const e = error as { httpCode?: string | number; statusCode?: number; message?: string };
	return String(e.httpCode) === '404' || e.statusCode === 404 || /not found/i.test(String(e.message || ''));
}

/** POST /v1/runs/start; if the agent does not exist yet, register it with the cadence from the node and try again. */
async function startRun(
	ctx: IExecuteFunctions,
	agent: string,
	source: string,
	meta: IDataObject,
	cadenceMin: number,
	graceMin: number,
): Promise<IDataObject> {
	try {
		return await runVouchRequest(ctx, 'POST', '/v1/runs/start', { agent, source, meta });
	} catch (error) {
		if (!isNotFound(error)) throw new NodeApiError(ctx.getNode(), error as JsonObject);
	}
	await runVouchRequest(ctx, 'POST', '/v1/agents', {
		name: agent,
		cadence_s: Math.max(60, Math.round(cadenceMin * 60)),
		grace_s: Math.max(60, Math.round(graceMin * 60)),
	});
	return await runVouchRequest(ctx, 'POST', '/v1/runs/start', { agent, source, meta });
}

function parseJsonField(ctx: IExecuteFunctions, raw: unknown, field: string, i: number): IDataObject {
	if (raw === undefined || raw === null || raw === '') return {};
	if (typeof raw === 'object') return raw as IDataObject;
	try {
		const parsed = JSON.parse(String(raw)) as unknown;
		if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed as IDataObject;
	} catch {
		// fall through to the error below
	}
	throw new NodeOperationError(ctx.getNode(), `${field} must be a JSON object, for example {"rows_written": true}`, {
		itemIndex: i,
	});
}

export class RunVouch implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'RunVouch',
		name: 'runVouch',
		icon: { light: 'file:runvouch.svg', dark: 'file:runvouch.dark.svg' },
		usableAsTool: true,
		group: ['transform'],
		version: 1,
		subtitle: '={{$parameter["operation"]}}',
		description:
			'Heartbeat monitoring for scheduled workflows: report a run to RunVouch and get an alert when the schedule stops firing, the workflow fails, or it finishes without evidence',
		defaults: {
			name: 'RunVouch',
		},
		inputs: [NodeConnectionTypes.Main],
		outputs: [NodeConnectionTypes.Main],
		credentials: [
			{
				name: 'runVouchApi',
				required: true,
			},
		],
		properties: [
			{
				displayName: 'Operation',
				name: 'operation',
				type: 'options',
				noDataExpression: true,
				options: [
					{
						name: 'Start Run',
						value: 'start',
						description: 'Report that a run has started; returns a run ID to pass to End Run',
						action: 'Start a run',
					},
					{
						name: 'End Run',
						value: 'end',
						description: 'Report that a run has finished, with status and evidence',
						action: 'End a run',
					},
					{
						name: 'Heartbeat',
						value: 'heartbeat',
						description: 'Start and end a run in one step (a plain check-in, like pinging a heartbeat URL)',
						action: 'Send a heartbeat',
					},
				],
				default: 'start',
			},
			{
				displayName: 'Agent Name',
				name: 'agent',
				type: 'string',
				default: '',
				required: true,
				placeholder: 'lead-enricher',
				description:
					'The name of the monitored job in RunVouch. Use one name per workflow. The first run registers it with the cadence below.',
				displayOptions: {
					show: {
						operation: ['start', 'heartbeat'],
					},
				},
			},
			{
				displayName: 'Expected Every (Minutes)',
				name: 'cadenceMinutes',
				type: 'number',
				default: 60,
				typeOptions: { minValue: 1 },
				description:
					'How often this workflow is scheduled to run. Used once, when the agent is registered on its first run; change it later with rv agent or in the dashboard.',
				displayOptions: {
					show: {
						operation: ['start', 'heartbeat'],
					},
				},
			},
			{
				displayName: 'Grace Period (Minutes)',
				name: 'graceMinutes',
				type: 'number',
				default: 15,
				typeOptions: { minValue: 1 },
				description:
					'How late a run may be before RunVouch raises MISSED. Also used only at first registration.',
				displayOptions: {
					show: {
						operation: ['start', 'heartbeat'],
					},
				},
			},
			{
				displayName: 'Run ID',
				name: 'runId',
				type: 'string',
				default: '={{ $("RunVouch Start").item.json.run_id }}',
				required: true,
				description: 'The run_id returned by the Start Run operation',
				displayOptions: {
					show: {
						operation: ['end'],
					},
				},
			},
			{
				displayName: 'Status',
				name: 'status',
				type: 'options',
				options: [
					{ name: 'OK', value: 'ok' },
					{ name: 'Fail', value: 'fail' },
				],
				default: 'ok',
				description: 'Whether the run did its job. Use an expression to derive this from earlier nodes.',
				displayOptions: {
					show: {
						operation: ['end', 'heartbeat'],
					},
				},
			},
			{
				displayName: 'Evidence',
				name: 'evidence',
				type: 'json',
				default: '',
				placeholder: '{"rows_written": {{ $json.count > 0 }}}',
				description:
					'A JSON object of named checks, each true or false, evaluated in n8n: {"rows_written": true}. Any false value raises NO_EVIDENCE: the workflow was green but the work did not happen. The README shows a server-side check that a web address answers 200.',
				displayOptions: {
					show: {
						operation: ['end', 'heartbeat'],
					},
				},
			},
			{
				displayName: 'Additional Fields',
				name: 'additionalFields',
				type: 'collection',
				placeholder: 'Add Field',
				default: {},
				options: [
					{
						displayName: 'Cost (USD)',
						name: 'cost',
						type: 'number',
						default: 0,
						description: 'What this run cost, for the daily and per-run cost caps',
					},
					{
						displayName: 'Tokens',
						name: 'tokens',
						type: 'number',
						default: 0,
						description: 'LLM tokens used by this run, if known',
					},
					{
						displayName: 'Meta',
						name: 'meta',
						type: 'json',
						default: '',
						description: 'Free-form JSON object stored with the run (for example the workflow execution ID)',
					},
					{
						displayName: 'Source',
						name: 'source',
						type: 'string',
						default: 'n8n',
						description: 'Where the run came from; shown in the dashboard',
					},
				],
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];
		const operation = this.getNodeParameter('operation', 0) as Op;

		for (let i = 0; i < items.length; i++) {
			try {
				const additional = this.getNodeParameter('additionalFields', i, {}) as IDataObject;
				const source = String(additional.source || 'n8n');
				const meta = parseJsonField(this, additional.meta, 'Meta', i);
				if (!meta.n8n_execution_id) meta.n8n_execution_id = this.getExecutionId();
				if (!meta.n8n_workflow) meta.n8n_workflow = this.getWorkflow().name;

				let result: IDataObject;

				if (operation === 'start') {
					result = await startRun(
						this,
						this.getNodeParameter('agent', i) as string,
						source,
						meta,
						this.getNodeParameter('cadenceMinutes', i, 60) as number,
						this.getNodeParameter('graceMinutes', i, 15) as number,
					);
				} else if (operation === 'end') {
					const runId = this.getNodeParameter('runId', i) as string;
					if (!runId) {
						throw new NodeOperationError(this.getNode(), 'Run ID is empty; connect this node after a RunVouch Start Run node', {
							itemIndex: i,
						});
					}
					result = await runVouchRequest(this, 'POST', '/v1/runs/end', {
						run_id: runId,
						status: this.getNodeParameter('status', i) as string,
						evidence: parseJsonField(this, this.getNodeParameter('evidence', i, ''), 'Evidence', i),
						cost: Number(additional.cost || 0),
						tokens: Number(additional.tokens || 0),
						meta,
					});
					result.run_id = runId;
				} else {
					const started = await startRun(
						this,
						this.getNodeParameter('agent', i) as string,
						source,
						meta,
						this.getNodeParameter('cadenceMinutes', i, 60) as number,
						this.getNodeParameter('graceMinutes', i, 15) as number,
					);
					const runId = String(started.run_id);
					result = await runVouchRequest(this, 'POST', '/v1/runs/end', {
						run_id: runId,
						status: this.getNodeParameter('status', i) as string,
						evidence: parseJsonField(this, this.getNodeParameter('evidence', i, ''), 'Evidence', i),
						cost: Number(additional.cost || 0),
						tokens: Number(additional.tokens || 0),
						meta,
					});
					result.run_id = runId;
				}

				returnData.push({ json: result, pairedItem: { item: i } });
			} catch (error) {
				if (this.continueOnFail()) {
					returnData.push({ json: { error: (error as Error).message }, pairedItem: { item: i } });
					continue;
				}
				if (error instanceof NodeOperationError || error instanceof NodeApiError) {
					throw new NodeOperationError(this.getNode(), error, { itemIndex: i });
				}
				throw new NodeApiError(this.getNode(), error as JsonObject, { itemIndex: i });
			}
		}

		return [returnData];
	}
}

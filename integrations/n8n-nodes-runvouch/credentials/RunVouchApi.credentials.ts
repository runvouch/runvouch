import type {
	IAuthenticateGeneric,
	Icon,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class RunVouchApi implements ICredentialType {
	name = 'runVouchApi';

	icon: Icon = { light: 'file:../nodes/RunVouch/runvouch.svg', dark: 'file:../nodes/RunVouch/runvouch.dark.svg' };

	displayName = 'RunVouch API';

	documentationUrl = 'https://runvouch.com/docs/n8n';

	properties: INodeProperties[] = [
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			description:
				'Your RunVouch API key (starts with rv_). Get a free key at https://runvouch.com; three agents are free.',
		},
		{
			displayName: 'API URL',
			name: 'baseUrl',
			type: 'string',
			default: 'https://api.runvouch.com',
			description: 'Leave the default unless you self-host RunVouch',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				'X-API-Key': '={{$credentials.apiKey}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/v1/agents',
			method: 'GET',
		},
	};
}

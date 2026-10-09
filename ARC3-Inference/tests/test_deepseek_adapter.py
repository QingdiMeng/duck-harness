import unittest

from inference.utils.openai_compat import build_chat_payload


class DeepSeekPayloadTests(unittest.TestCase):
    def payload(self, provider='deepseek', thinking=True, **kwargs):
        return build_chat_payload(provider=provider, model='test', messages=[], max_tokens=4096,
                                  temperature=0.6, top_p=0.95, top_k=20, thinking=thinking,
                                  tools=[], seed=42, **kwargs)

    def test_thinking_payload_does_not_send_vllm_options(self):
        p = self.payload()
        self.assertEqual(p['thinking'], {'type': 'enabled'})
        self.assertEqual(p['max_tokens'], 4096)
        for k in ['temperature', 'top_k', 'seed', 'chat_template_kwargs']:
            self.assertNotIn(k, p)

    def test_non_thinking_and_existing_vllm(self):
        p = self.payload(thinking=False)
        self.assertEqual(p['thinking'], {'type': 'disabled'})
        self.assertEqual(p['temperature'], 0.6)
        p = self.payload(provider='vllm')
        self.assertEqual(p['chat_template_kwargs'], {'enable_thinking': True})
        self.assertEqual(p['top_k'], 20)
        self.assertNotIn('thinking', p)

    def test_unspecified_output_limit_is_omitted(self):
        p = build_chat_payload(provider='deepseek', model='test', messages=[],
                               max_tokens=None, temperature=0.6, top_p=0.95,
                               top_k=0, thinking=True)
        self.assertNotIn('max_tokens', p)
        self.assertEqual(p['thinking'], {'type': 'enabled'})

    def test_vllm_unspecified_output_limit_is_omitted(self):
        p = build_chat_payload(provider='vllm', model='test', messages=[],
                               max_tokens=None, temperature=1.0, top_p=0.95,
                               top_k=20, thinking=True)
        self.assertNotIn('max_tokens', p)
        self.assertNotIn('max_completion_tokens', p)

    def test_reasoning_history_is_verbatim_and_original_not_mutated(self):
        raw = '  reasoning\n\nwith whitespace  '
        messages = [{'role': 'assistant', 'content': '', 'reasoning': 'display',
                     'reasoning_content': raw, 'tool_calls': []}]
        p = build_chat_payload(provider='deepseek', model='test', messages=messages,
                               max_tokens=4096, temperature=0.6, top_p=0.95,
                               top_k=20, thinking=True)
        self.assertEqual(p['messages'][0]['reasoning_content'], raw)
        self.assertNotIn('reasoning', p['messages'][0])
        self.assertEqual(messages[0]['reasoning'], 'display')


if __name__ == '__main__':
    unittest.main()

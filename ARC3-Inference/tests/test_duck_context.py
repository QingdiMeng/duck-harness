import unittest

from inference.agent.tool_agent import ToolAgent


def exchange(call_id, text='small'):
    return [
        {'role': 'assistant', 'content': text, 'tool_calls': [
            {'id': call_id, 'type': 'function', 'function': {'name': 'python', 'arguments': '{}'}}]},
        {'role': 'tool', 'tool_call_id': call_id, 'content': 'result-' + call_id},
    ]


class ContextRetentionTests(unittest.TestCase):
    def agent(self, budget=500):
        agent = ToolAgent.__new__(ToolAgent)
        agent._context_budget_tokens = budget
        return agent

    def test_current_user_and_latest_tool_result_survive_budget_trim(self):
        user = {'role': 'user', 'content': [{'type': 'text', 'text': 'current board'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AAAA'}}]}
        messages = [{'role': 'system', 'content': 'rules'}, user,
                    *exchange('old', 'x' * 6000), *exchange('new')]
        trimmed = self.agent()._trim_messages_for_context(messages)
        self.assertEqual(trimmed, [messages[0], user, *exchange('new')])

    def test_older_game_turn_is_removed_before_current_turn(self):
        messages = [{'role': 'system', 'content': 'rules'},
                    {'role': 'user', 'content': 'old' * 2000}, *exchange('old'),
                    {'role': 'user', 'content': 'current'}, *exchange('new')]
        self.assertEqual(self.agent()._trim_messages_for_context(messages),
                         [messages[0], *messages[4:]])

    def test_persistent_turn_limit_does_not_empty_history(self):
        user = {'role': 'user', 'content': 'current board'}
        messages = [{'role': 'system', 'content': 'rules'}, user]
        for i in range(35):
            messages.extend(exchange(str(i)))
        history = self.agent(100000)._persistent_history_messages(messages)
        self.assertTrue(history)
        self.assertEqual(history[0], user)
        self.assertEqual(history[-2:], exchange('34'))
        self.assertEqual(sum(m['role'] == 'assistant' for m in history), 30)

    def test_forced_reduction_preserves_tool_pair_and_user(self):
        messages = [{'role': 'system', 'content': 'rules'},
                    {'role': 'user', 'content': 'current'}, *exchange('old'), *exchange('new')]
        self.assertEqual(self.agent()._force_reduce_messages(messages),
                         [*messages[:2], *exchange('new')])

    def test_oversized_latest_turn_is_kept_intact(self):
        messages = [{'role': 'system', 'content': 'rules'},
                    {'role': 'user', 'content': 'current'}, *exchange('new', 'x' * 6000)]
        self.assertEqual(self.agent()._trim_messages_for_context(messages), messages)


if __name__ == '__main__':
    unittest.main()

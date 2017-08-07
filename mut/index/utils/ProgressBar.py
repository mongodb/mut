import time
import math


class Section:
    def __init__(self, header: str='', output: str='', data={}) -> None:
        '''Generiec progress bar section interface.'''
        self.header = header
        self.output = output
        self.data = data
        self.width = 0

    def update(self):
        '''Custom logic to update the section.'''
        pass


class Timer(Section):
    '''Display a running timer of how long the parser has been running.'''
    def __init__(self, start_time: float, rpadding: int=0) -> None:
        super().__init__()
        self.header = 'Elapsed Time'
        self.output = '{elapsed_time: 3.3f} (s)'
        self.data = {
            'elapsed_time': 0
        }
        self.start_time = start_time
        self.width = len(self.header+':') + rpadding  # 13

    def update(self):
        '''Update the timer everytime a document is parsed.'''
        self.data['elapsed_time'] = round(time.time() - self.start_time, 3)


class Percentage(Section):
    '''Display a progress bar and percentage completed indicator.'''
    def __init__(self, num_documents: int, rpadding: int=0) -> None:
        super().__init__()
        self.header = 'Progress'
        self.output = '|{done}{todo}|{percent_done: 2.2f}%'
        self.data = {
            'percent_done': 0,
            'done': '',
            'todo': ' ' * 30
        }
        self.width = 39 + rpadding
        self.num_documents = num_documents

    def update(self, num_processed):
        self.data['percent_done'] = 100*(num_processed / self.num_documents)
        num_done = math.floor(30*self.data['percent_done']/100)
        self.data['done'] = u'\u2588' * num_done
        self.data['todo'] = ' ' * (30 - num_done)


class Counter(Section):
    '''Display a count of finished items vs total items.'''
    def __init__(self, num_documents: int, rpadding: int=0) -> None:
        super().__init__()
        self.header = 'Files'
        self.output = '[{num_processed} / {num_documents}]'
        self.data = {
            'num_processed': 0,
            'num_documents': int(num_documents)
        }
        self.width = 5 + 2*len(str(num_documents)) + rpadding

    def update(self, num_processed):
        self.data['num_processed'] = num_processed


class CurrentFile(Section):
    '''Display the last file to have been successfully parsed.'''
    def __init__(self, rpadding: int=0) -> None:
        super().__init__()
        self.header = 'Last Processed File'
        self.output = '{current_file}'
        self.data = {
            'current_file': ''
        }
        self.width = len(self.header+':') + rpadding

    def update(self, current_file):
        self.data['current_file'] = current_file
        self.width = len(current_file)


class ProgressBar():
    '''Display a progress bar for the parser.'''
    def __init__(self, num_documents: int, start_time: float) -> None:
        self.sections = {
            'Timer': Timer(start_time, rpadding=4),
            'Percentage': Percentage(num_documents, rpadding=4),
            'Counter': Counter(num_documents, rpadding=4),
            'CurrentFile': CurrentFile()
        }
        self.num_processed = 0
        self.build()

    def build(self) -> None:
        '''Print the progress bar to stdout.'''
        self._print_header_row()
        self._print_sections()

    def update(self, processed_file_name):
        '''Update the progress bar aftern a successful parse.'''
        self.num_processed += 1
        for section in self.sections.values():
            arg_options = {
                'num_processed': self.num_processed,
                'current_file': processed_file_name
            }
            kwargs = {arg: arg_options[arg]
                      for arg in section.update.__code__.co_varnames
                      if arg is not 'self' and arg in arg_options}
            section.update(**kwargs)
        self._print_sections()

    def _print_header_row(self) -> None:
        header_row = ''
        for section in self.sections.values():
            header_row += (section.header + ':').ljust(section.width, ' ')
        print(header_row)

    def _print_sections(self) -> None:
        row = ''
        for section in self.sections.values():
            out = section.output.format(**section.data)
            row += out.ljust(section.width, " ")
        print("\033[K", end='\r')
        print(row, end='\r')

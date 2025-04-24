from graphviz import Digraph

def create_learning_platform_flowchart():
    dot = Digraph('Learning Platform Flowchart', format='png')
    dot.attr(rankdir='TB', size='10')

    dot.node('Data collection on major learning websites', shape='box')
    dot.node('Data collation and classification', shape='box')
    dot.node('Update the initial training data', shape='box', style='filled', fillcolor='lightgrey')
    dot.node('Provide personal advice', shape='box')
    dot.node('Personalized question bots', shape='box')
    dot.node('Student-side answer data collection', shape='box')
    dot.node('Statistical model analysis', shape='box')
    dot.node('Demanders', shape='box')

    dot.edge('Data collection on major learning websites', 'Data collation and classification', label='Instant updates and version comparisons')
    dot.edge('Data collation and classification', 'Update the initial training data', label='Classification of each grade and subject')
    dot.edge('Update the initial training data', 'Provide personal advice')
    dot.edge('Provide personal advice', 'Personalized question bots')
    dot.edge('Personalized question bots', 'Student-side answer data collection')
    dot.edge('Student-side answer data collection', 'Statistical model analysis')
    dot.edge('Statistical model analysis', 'Update the initial training data')
    dot.edge('Personalized question bots', 'Demanders', label='Generate customized questionnaires')

    dot.render('learning_platform_flowchart', view=True)

create_learning_platform_flowchart()
#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Run this JavaScript on the user mapping page when importing:

(function ($) {
	var users = [];
	$('select[name^="user_map"] option').each(function () {
		users.push($(this).text().replace(/^\(|\s+SourceForge\)$/g, ''));
	});
	$('ol#authors li').each(function () {
		var author = $(this).find('strong').text().match(/\(([^)]+)\)/)[1],
			index = users.indexOf(author);
		if (index < 0) {
			$(this).find('input[name^="user_new"]').val(author + ' (SourceForge)');
			index = 0;
		}
		$(this).find('select[name^="user_map"]')[0].selectedIndex = index;
	})
})(jQuery)

"""

from __future__ import print_function
from collections import OrderedDict
import cgi
import json
import os
import re
import sys
import time
import unicodedata
import urllib


import markdown as _markdown


_allura_id_to_wpxml_id = {}
_id = 0
_slugs = []

revision_template = '''
<ul class="bbp-reply-revision-log">
	<li class="bbp-reply-revision-log-item">
		This %(post_type)s was modified on %(mtime)s by %(author)s.
	</li>
</ul>'''


def get_id(allura_id):
	global _id
	id = _allura_id_to_wpxml_id.get(allura_id)
	if not id:
		id = _allura_id_to_wpxml_id[allura_id] = _id
		_id += 1
	return id


def get_post_content(post, post_type):
	content = markdown(post['text'])
	if post['last_edited']:
		mtime = post['last_edited'].split('.')[0]
		content += revision_template % {'post_type': post_type, 'mtime': mtime,
										'author': post['author']}
	return content


def make_slug(title):
	slug = re.sub(r'[\s.-]+', '-',
				  re.sub(r'[^\w\s.-]', '',
						 unicodedata.normalize('NFKD',
											   title).encode('ascii',
															 'ignore')).strip().lower()).strip('-')
	original_slug = slug
	num = 1
	while slug in _slugs:
		num += 1
		slug = original_slug + '-%i' % num
	if num > 1:
		print(slug, file=sys.stderr)
	_slugs.append(slug)
	return slug


def markdown(text):
	html = cgi.escape(text)
	# Restore Markdown blockquoting
	html = re.sub(r'^&gt;', '>', html, flags=re.M)
	# Markdown to WP HTML
	html = _markdown.markdown(html, output_format='xhtml5')
	html = html.replace('</p>\n<p>', '\n\n')
	html = html.replace('<p>', '')
	html = html.replace('</p>', '')
	html = html.replace('<blockquote>\n', '<blockquote>')
	html = html.replace('\n</blockquote>', '</blockquote>')
	return html


class WPXML_Item(OrderedDict):

	def __init__(self, parent, id, post_type, title, base_url,
				 link='%(base_url)s?post_type=%(post_type)s&p=%(id)s',
				 date_time=None, creator='', guid=None, post_name=None,
				 content='', comment_status='open', ping_status='open',
				 menu_order=0, post_password='', is_sticky=False,
				 status='publish', excerpt=''):
		OrderedDict.__init__(self)
		id = get_id(id)
		self.items = []
		self.postmeta = OrderedDict()
		if date_time:
			timestamp = time.strptime(date_time.split('.')[0], '%Y-%m-%d %H:%M:%S')
			timestamp_gmt = time.gmtime(time.mktime(timestamp))
		else:
			timestamp = time.localtime()
			timestamp_gmt = time.gmtime()
		self.timestamp = timestamp
		self.timestamp_gmt = timestamp
		if not post_name:
			if title:
				post_name = make_slug(title)
			else:
				post_name = id
		if re.search(r'%\(\w+\)[dfis]', link):
			link = link % locals()
		if not guid:
			guid = link
		content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]+', '', content)
		self.update([('title', cgi.escape(title)),
					 ('link', cgi.escape(link)),
					 ('pubDate', time.strftime('%a, %d %b %Y %H:%M:%S +0000', timestamp)),
					 ('dc:creator', cgi.escape(creator)),
					 ('guid', cgi.escape(guid)),
					 ('description', ''),
					 ('content:encoded', content),
					 ('excerpt:encoded', excerpt),
					 ('wp:post_id', id),
					 ('wp:post_date', time.strftime('%Y-%m-%d %H:%M:%S', timestamp)),
					 ('wp:post_date_gmt', time.strftime('%Y-%m-%d %H:%M:%S', timestamp_gmt)),
					 ('wp:comment_status', comment_status),
					 ('wp:ping_status', ping_status),
					 ('wp:post_name', post_name),
					 ('wp:status', status),
					 ('wp:post_parent', parent.get('wp:post_id', 0)),
					 ('wp:menu_order', menu_order),
					 ('wp:post_type', post_type),
					 ('wp:post_password', cgi.escape(post_password)),
					 ('wp:is_sticky', int(is_sticky))])

	@property
	def xml(self):
		"""	Example output:

	<item>
		<title>Test-Forum</title>
		<link>http://example.com/forums/forum/test-forum/</link>
		<pubDate>Wed, 12 Aug 2015 00:22:03 +0000</pubDate>
		<dc:creator><![CDATA[johndoe]]></dc:creator>
		<guid isPermaLink="false">http://example.com/?post_type=forum&#038;p=123</guid>
		<description></description>
		<content:encoded><![CDATA[Lorem ipsum dolor sit amet.]]></content:encoded>
		<excerpt:encoded><![CDATA[]]></excerpt:encoded>
		<wp:post_id>123</wp:post_id>
		<wp:post_date><![CDATA[2015-08-12 02:22:03]]></wp:post_date>
		<wp:post_date_gmt><![CDATA[2015-08-12 00:22:03]]></wp:post_date_gmt>
		<wp:comment_status><![CDATA[closed]]></wp:comment_status>
		<wp:ping_status><![CDATA[open]]></wp:ping_status>
		<wp:post_name><![CDATA[test-forum]]></wp:post_name>
		<wp:status><![CDATA[publish]]></wp:status>
		<wp:post_parent>0</wp:post_parent>
		<wp:menu_order>0</wp:menu_order>
		<wp:post_type><![CDATA[forum]]></wp:post_type>
		<wp:post_password><![CDATA[]]></wp:post_password>
		<wp:is_sticky>0</wp:is_sticky>
		<wp:postmeta>
			<wp:meta_key><![CDATA[_edit_last]]></wp:meta_key>
			<wp:meta_value><![CDATA[1]]></wp:meta_value>
		</wp:postmeta>
		<wp:postmeta>
			<wp:meta_key><![CDATA[_bbp_last_active_time]]></wp:meta_key>
			<wp:meta_value><![CDATA[2015-09-18 15:45:19]]></wp:meta_value>
		</wp:postmeta>
		<wp:postmeta>
			<wp:meta_key><![CDATA[_bbp_forum_subforum_count]]></wp:meta_key>
			<wp:meta_value><![CDATA[0]]></wp:meta_value>
		</wp:postmeta>
		<wp:postmeta>
			<wp:meta_key><![CDATA[_bbp_reply_count]]></wp:meta_key>
			<wp:meta_value><![CDATA[0]]></wp:meta_value>
		</wp:postmeta>
		<wp:postmeta>
			<wp:meta_key><![CDATA[_bbp_total_reply_count]]></wp:meta_key>
			<wp:meta_value><![CDATA[0]]></wp:meta_value>
		</wp:postmeta>
		<wp:postmeta>
			<wp:meta_key><![CDATA[_bbp_topic_count]]></wp:meta_key>
			<wp:meta_value><![CDATA[0]]></wp:meta_value>
		</wp:postmeta>
		<wp:postmeta>
			<wp:meta_key><![CDATA[_bbp_total_topic_count]]></wp:meta_key>
			<wp:meta_value><![CDATA[0]]></wp:meta_value>
		</wp:postmeta>
		<wp:postmeta>
			<wp:meta_key><![CDATA[_bbp_topic_count_hidden]]></wp:meta_key>
			<wp:meta_value><![CDATA[0]]></wp:meta_value>
		</wp:postmeta>
	</item>

"""
		xml = '	<item>\n'
		for key, value in self.iteritems():
			if key == 'guid':
				xml += '		<%s isPermaLink="false">' % key
			else:
				xml += '		<%s>' % key
			if key in ('title', 'link', 'pubDate', 'guid', 'description',
					   'wp:post_id', 'wp:post_parent', 'wp:menu_order',
					   'wp:is_sticky'):
				xml += unicode(value)
			elif value:
				xml += '<![CDATA[%s]]>' % value
			xml += '</%s>\n' % key
		for meta_key, meta_value in self.postmeta.iteritems():
			xml += '		<wp:postmeta>\n'
			xml += '			<wp:meta_key><![CDATA[%s]]></wp:meta_key>\n' % meta_key
			xml += '			<wp:meta_value><![CDATA[%s]]></wp:meta_value>\n' % unicode(meta_value)
			xml += '		</wp:postmeta>\n'
		xml += '	</item>\n'
		for item in self.items:
			xml += item.xml
		return xml.encode('UTF-8')


class Allura2WPXML():

	def __init__(self, json_filename, start_id=1, base_url='', creator='',
				 include_attachments='all',
				 post_date_range=[(0, 0, 0), time.localtime()]):
		global _id
		_id = start_id
		self.include_attachments = include_attachments
		self.items = []
		with open(json_filename, 'r') as json_file:
			allura_dict = json.load(json_file)
		for key, item in allura_dict.iteritems():
			if key == 'forums':
				total_reply_count = 0
				for forum in item:
					wpxml_forum = WPXML_Item({}, forum['_id'],
											 'forum', forum['name'], base_url,
											 '%(base_url)sforums/forum/%(post_name)s/',
											 None, creator, None, None,
											 markdown(forum['description']), 'closed')
					self.items.append(wpxml_forum)
					# Get topics
					forum_last_active = time.localtime(0)
					forum_last_reply_id = 0
					forum_last_active_id = 0
					topic_count = 0
					total_reply_count = 0
					last_topic_id = 0
					for thread in forum['threads']:
						if not thread['posts']:
							continue
						post_timestamp = time.strptime(thread['posts'][-1]['timestamp'].split('.')[0],
													   '%Y-%m-%d %H:%M:%S')
						if (post_timestamp[:3] < post_date_range[0][:3] or 
							post_timestamp[:3] > post_date_range[1][:3]):
							continue
						last_active = time.localtime(0)
						last_reply_id = 0
						last_active_id = 0
						voices = set()
						post1 = thread['posts'][0]
						post_name = make_slug(thread['subject'] + '-' + thread['_id'])
						wpxml_topic = WPXML_Item(wpxml_forum, thread['_id'],
												 'topic', thread['subject'],
												 base_url,
												 '%(base_url)sforums/topic/%(post_name)s/',
												 post1['timestamp'],
												 post1['author'], None, post_name,
												 get_post_content(post1, 'topic'),
												 'closed')
						self.items.append(wpxml_topic)
						if wpxml_topic.timestamp > last_active:
							last_active = wpxml_topic.timestamp
							last_active_id = wpxml_topic['wp:post_id']
						if wpxml_topic.timestamp > forum_last_active:
							forum_last_active = last_active
							forum_last_active_id = last_active_id
							last_topic_id = wpxml_topic['wp:post_id']
						topic_count += 1
						self._add_attachments(post1, wpxml_topic)
						# Get replies
						reply_count = 0
						posts = thread['posts']
						parent_ids = []
						ordered_posts = []
						for post in posts:
							parent_slug = '/'.join(post['slug'].split('/')[:-1])
							if '/' in post['slug'] and (thread['_id'], parent_slug) in parent_ids:
								index = parent_ids.index((thread['_id'], parent_slug))
								parent_ids.insert(index + 1, (thread['_id'], post['slug']))
								ordered_posts.insert(index + 1, post)
							else:
								parent_ids.append((thread['_id'], post['slug']))
								ordered_posts.append(post)
						for i, post in enumerate(ordered_posts[1:]):
							wpxml_reply = WPXML_Item(wpxml_topic, (thread['_id'], post['slug']),
													 'reply', '',
													 base_url,
													 '%(base_url)sforums/reply/%(id)s/',
													 post['timestamp'],
													 post['author'], None, None,
													 get_post_content(post, 'reply'),
													 'closed', 'closed',
													 i + 1)
							self.items.append(wpxml_reply)
							voices.add(post['author'])
							if wpxml_reply.timestamp > last_active:
								last_active = wpxml_reply.timestamp
								last_active_id = wpxml_reply['wp:post_id']
							if wpxml_reply.timestamp > forum_last_active:
								forum_last_active = last_active
								forum_last_active_id = last_active_id
								last_topic_id = wpxml_topic['wp:post_id']
								forum_last_reply_id = wpxml_reply['wp:post_id']
							last_reply_id = wpxml_reply['wp:post_id']
							reply_count += 1
							wpxml_reply.postmeta.update([('_bbp_author_ip', '0.0.0.0'),
														 ('_bbp_forum_id', wpxml_forum['wp:post_id']),
														 ('_bbp_topic_id', wpxml_topic['wp:post_id'])])
							if '/' in post['slug']:
								parent_slug = '/'.join(post['slug'].split('/')[:-1])
								wpxml_reply.postmeta['_bbp_reply_to'] = get_id((thread['_id'], parent_slug))
							self._add_attachments(post, wpxml_reply)
						total_reply_count += reply_count
						wpxml_topic.postmeta.update([('_bbp_last_active_time', time.strftime('%Y-%m-%d %H:%M:%S', last_active)),
													 ('_bbp_reply_count', reply_count),
													 ('_bbp_reply_count_hidden', 0),
													 ('_bbp_last_reply_id', last_reply_id),  # Post
													 ('_bbp_last_active_id', last_active_id),  # Post
													 ('_bbp_author_ip', '0.0.0.0'),
													 ('_bbp_forum_id', wpxml_forum['wp:post_id']),
													 ('_bbp_topic_id', wpxml_topic['wp:post_id']),
													 ('_bbp_voice_count', len(voices))])
					wpxml_forum.postmeta.update([('_bbp_last_active_time', time.strftime('%Y-%m-%d %H:%M:%S', forum_last_active)),
												 ('_bbp_forum_subforum_count', 0),
												 ('_bbp_reply_count', total_reply_count),
												 ('_bbp_total_reply_count', total_reply_count),
												 ('_bbp_topic_count', topic_count),
												 ('_bbp_total_topic_count', topic_count),
												 ('_bbp_topic_count_hidden', 0),
												 ('_bbp_last_topic_id', last_topic_id),
												 ('_bbp_last_reply_id', forum_last_reply_id),  # Post
												 ('_bbp_last_active_id', forum_last_active_id)])  # Post

	def _add_attachments(self, post, parent):
		for attachment in post['attachments']:
			title = urllib.unquote(os.path.basename(attachment['url']).encode('utf8')).decode('utf8')
			post_name = make_slug(title + '-' + post['slug'])
			wpxml_attachment = WPXML_Item(parent,
										  attachment['url'],
										  'attachment',
										  title,
										  '',
										  attachment['url'],
										  post['timestamp'],
										  post['author'], None, post_name,
										  '', 'open', 'open',
										  excerpt=parent['wp:post_id'],
										  status='inherit')
			self.items.append(wpxml_attachment)
			wpxml_attachment['wp:attachment_url'] = attachment['url']

	@property
	def xml(self):
		xml = '''<rss version="2.0"
	xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
	xmlns:content="http://purl.org/rss/1.0/modules/content/"
	xmlns:wfw="http://wellformedweb.org/CommentAPI/"
	xmlns:dc="http://purl.org/dc/elements/1.1/"
	xmlns:wp="http://wordpress.org/export/1.2/"
>

<channel>
	<wp:wxr_version>1.2</wp:wxr_version>
'''
		for item in self.items:
			if (item['wp:post_type'] != 'attachment' and
				self.include_attachments != 'only') or (item['wp:post_type'] == 'attachment' and
														self.include_attachments in ('all', 'only')):
				xml += item.xml
		xml += '''</channel>
</rss>
'''
		return xml


def main(json_filename, start_id=1, base_url='', creator='',
		 include_attachments='all', post_date_range='0001-01-01_' +
												  time.strftime('%Y-%m-%d')):
	post_date_range = [time.strptime(date, '%Y-%m-%d')
					   for date in post_date_range.split('_')]
	print('Allura JSON filename:', json_filename, file=sys.stderr)
	print('WordPress post start ID:', start_id, file=sys.stderr)
	print('Base URL:', base_url, file=sys.stderr)
	print('WordPress post author:', creator, file=sys.stderr)
	print('Include attachments:', include_attachments, file=sys.stderr)
	print('Post date range:', ' to '.join([time.strftime('%Y-%m-%d', date)
										   for date in post_date_range]),
		  file=sys.stderr)
	print(Allura2WPXML(json_filename, int(start_id), base_url, creator,
					   include_attachments, post_date_range).xml)


if __name__ == '__main__':
	if not sys.argv[1:]:
		print("Usage:", os.path.basename(__file__),
			  "json_filename start_id base_url author_username "
			  "[include_attachments] [post_date_range]", file=sys.stderr)
		print('start_id              WordPress post start ID', file=sys.stderr)
		print('base_url              WordPress base URL', file=sys.stderr)
		print('author_username       WordPress username to use for attachments',
		      file=sys.stderr)
		print('include_attachments   Include attachments? (all|none|only, default all)',
			  file=sys.stderr)
		print('post_date_range       Posts to include from_to YYYY-mm-dd_YYYY-mm-dd',
			  file=sys.stderr)
	else:
		main(*sys.argv[1:])

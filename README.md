syncimap
=========

IMAP sync tool

Copy emails and folders from an IMAP account to another.
Creates missing folders and skips existing messages (using message-id).


This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.


based on IMAP Copy, author Gabriele Tozzi <gabriele@tozzi.eu>
https://github.com/gtozzi/imapcp

inspired by imapsync.pl, http://www.linux-france.org/prj/imapsync/



Example: to synchronise imap account "test1" on "imap.server1"
                    to  imap account "test2" on "imap.server2"
                    with user1 password "secret1,                    
                    with user2 password "secret2,                    
                    and exclude source folders, begins with "^Public|^Koncept|^Kalend|^Kontakt",                    
                    delete messages on the destination imap server that are not on the source server                    
                    with SSL connect to source imap server                    

syncimap \\
        --ssl1 ---delete2 --expunge2 --exclude "^Public|^Koncept|^Kalend|^Kontakt" \\
        --host1 imap.server1 --user1 test1 --password1 secret1 \\
        --host2 imap.server2 --user2 test2 --password2 secret2 
